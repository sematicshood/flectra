# Part of Flectra See LICENSE file for full copyright and licensing details.
from datetime import datetime, timedelta

from dateutil.relativedelta import relativedelta
from flectra import api, fields, models, _
from flectra.addons import decimal_precision as dp
from flectra.exceptions import ValidationError, UserError
from flectra.tools import DEFAULT_SERVER_DATETIME_FORMAT, float_compare
from flectra.tools.misc import formatLang


class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    @api.model
    def _default_warehouse_id(self):
        company = self.env.user.company_id.id
        warehouse_ids = self.env['stock.warehouse'].search([
            ('company_id', '=', company)], limit=1)
        return warehouse_ids

    READONLY_STATES = {
        'open': [('readonly', True)],
        'done': [('readonly', True)],
        'cancel': [('readonly', True)],
    }

    @api.model
    def _default_picking_type(self):
        type_obj = self.env['stock.picking.type']
        inv_type = self.env.context.get('type', False)
        company_id = \
            self.env.context.get('company_id') or self.env.user.company_id.id
        branch_id = self.env.context.get(
            'branch_id') or self.env.user.default_branch_id.id
        type_code = 'outgoing'
        if inv_type in ['out_invoice'] and self.env.context.get(
                'filter_refund'):
            type_code = 'incoming'
        elif inv_type in ['out_invoice', 'in_refund']:
            type_code = 'outgoing'
        elif inv_type in ['out_refund', 'in_invoice']:
            type_code = 'incoming'
        types = type_obj.search([('code', '=', type_code),
                                 ('warehouse_id.company_id', '=', company_id),
                                 ('warehouse_id.branch_id', '=', branch_id)])
        if not types:
            types = type_obj.search([
                ('code', '=', 'incoming'), ('warehouse_id', '=', False)])
        return types[:1]

    @api.depends('invoice_line_ids.date_planned')
    def _compute_date_planned(self):
        for invoice in self:
            min_date = fields.Date.today()
            for line in invoice.invoice_line_ids:
                if not min_date or line.date_planned and \
                        line.date_planned < min_date:
                    min_date = line.date_planned
            if min_date:
                invoice.date_planned = min_date

    @api.multi
    @api.returns('self')
    def refund(self, date_invoice=None,
               date=None, description=None, journal_id=None):
        result = super(AccountInvoice, self).refund(
            date_invoice=date_invoice, date=date,
            description=description, journal_id=journal_id)
        if self.env.context.get('filter_refund'):
            # delete old invoice lines
            result.invoice_line_ids.unlink()
            # Generate new invoice lines
            result.onchange_refund_invoice_id()
            result.write({
                'date_planned': result.refund_invoice_id.date_planned,
                'partner_shipping_id':
                    result.refund_invoice_id.partner_shipping_id.id})
        return result

    @api.onchange('refund_invoice_id')
    def onchange_refund_invoice_id(self):
        list_data = []
        value = {}
        data_dict = self.get_quantity_update(self)
        if self.type == 'out_refund':
            for line in self.refund_invoice_id.invoice_line_ids:
                remaining_qty = line.qty_delivered - data_dict.get(
                    line.product_id.id).get('quantity') if \
                    data_dict else line.qty_delivered
                if remaining_qty > 0:
                    list_data.append((0, 0, {
                        'product_id': line.product_id.id,
                        'name': line.name,
                        'date_planned': line.date_planned,
                        'account_id': line.account_id.id,
                        'account_analytic_id': line.account_analytic_id.id,
                        'analytic_tag_ids':
                            [(6, 0, line.analytic_tag_ids.ids)],
                        'uom_id': line.uom_id.id,
                        'quantity': remaining_qty,
                        'discount': line.discount,
                        'route_id': line.route_id.id,
                        'price_unit': line.price_unit,
                        'invoice_line_tax_ids':
                            [(6, 0, line.invoice_line_tax_ids.ids)],
                        'price_subtotal': line.price_subtotal,
                    }))
            value['invoice_line_ids'] = list_data
            self.origin = self.refund_invoice_id.number
            self.discount_method = self.refund_invoice_id.discount_method
            self.discount_amount = self.refund_invoice_id.discount_amount
            self.discount_per = self.refund_invoice_id.discount_per
            self.update(value)

    @api.model
    def create(self, vals):
        if vals.get('refund_invoice_id', False):
            refund_invoice_id = self.browse(vals.get('refund_invoice_id'))
            vals['origin'] = refund_invoice_id.number
        return super(AccountInvoice, self).create(vals)

    @api.multi
    def action_set_date_planned(self):
        for invoice_id in self:
            invoice_id.invoice_line_ids.update({
                'date_planned': invoice_id.date_planned})

    @api.multi
    def get_quantity_update(self, invoice):
        data_dict = {}
        if self.type != 'out_refund':
            return data_dict
        for inv in invoice.refund_invoice_id.refund_invoice_ids.filtered(
                lambda l: l.state in ['open', 'paid']):
            for line in inv.invoice_line_ids:
                if line.product_id.id not in data_dict:
                    data_dict[line.product_id.id] = \
                        {'quantity': line.qty_received}
                else:
                    data_dict[line.product_id.id]['quantity'] += \
                        line.qty_received
        return data_dict

    @api.multi
    def check_quantity(self):
        for invoice in self.filtered(
                lambda l: l.type in ['in_refund', 'out_refund']):
            data_dict = invoice.get_quantity_update(invoice)
            msg = 'Following Quantity is greater' \
                  ' than remaining qtyuantity!\n'
            check_warning = False
            if self.type == 'out_refund':
                for line in invoice.invoice_line_ids:
                    qty = sum(
                        [original_line.qty_delivered for original_line in
                         invoice.refund_invoice_id.invoice_line_ids
                         if line.product_id == original_line.product_id])
                    if data_dict:
                        remaining_qty = qty - data_dict.get(
                            line.product_id.id).get('quantity')
                    else:
                        remaining_qty = qty
                    if line.quantity > remaining_qty:
                        check_warning = True
                        msg += ("\n Product (%s) => Quantity (%s) should be "
                                "less than remaining quantity (%s)!") % (
                                   line.product_id.name,
                                   formatLang(self.env, line.quantity,
                                              digits=2),
                                   formatLang(self.env, remaining_qty,
                                              digits=2))
                if check_warning:
                    raise UserError(_(msg))

    @api.depends('refund_invoice_ids')
    def _compute_refund_invoice(self):
        for invoice in self:
            invoice.refund_invoice_count = len(invoice.refund_invoice_ids)

    @api.multi
    def action_view_refund_invoices(self):
        if self.type == 'out_invoice':
            action = self.env.ref(
                'account.action_invoice_refund_out_tree').read()[0]
            view_id = [(self.env.ref('account.invoice_form').id, 'form')]
        elif self.type == 'in_invoice':
            action = self.env.ref('account.action_invoice_in_refund').read()[0]
            view_id = \
                [(self.env.ref('account.invoice_supplier_form').id, 'form')]
        refund_invoice_ids = self.mapped('refund_invoice_ids')
        if len(refund_invoice_ids) > 1:
            action['domain'] = [('id', 'in', refund_invoice_ids.ids)]
        elif refund_invoice_ids:
            action['views'] = view_id
            action['res_id'] = refund_invoice_ids.id
        return action

    gst_invoice = fields.Selection(
        [('b2b', 'B2B'), ('b2cl', 'B2CL'), ('b2cs', 'B2CS'),
         ('b2bur', 'B2BUR')], string='GST Invoice',
        help='B2B Supplies: Taxable supplies made to other registered '
             'taxpayers.\n\nB2C Large [For outward supplies]: Taxable '
             'outward '
             'supplies to consumers where\na)The place of supply is '
             'outside the state where the supplier is registered and '
             'b)The '
             'total invoice value is more than the limit defined in '
             'company B2C lines.\ne.g., If in B2C line, B2CL limit is '
             'set to Rs 2,50,000 and invoice is of amount Rs 3,00,000 then'
             'invoice '
             'will be considered as of type B2CL.\n\nB2C Small '
             '[For outward supplies]: Supplies made to consumers and '
             'unregistered persons of the following nature\n'
             'a) Intra-State: any value b) Inter-State: Total invoice '
             'value is'
             ' less than the limit defined in company B2C lines.\n'
             'e.g., If in B2C line, B2CS limit is set to Rs 2,50,000 '
             '(for period 01-01-2017 to 31-12-2017) for inter state '
             'supply '
             'and invoice value is Rs 2,00,000 then invoice will be '
             'considered as of type B2CS.\n\nB2BUR [For inward supplies]: '
             'Inward supplies received from an unregistered supplier \n\n',
        copy=False)
    e_commerce_partner_id = fields.Many2one('res.partner',
                                            string='E-Commerce Partner')
    vat = fields.Char(string='GSTIN',
                      help='Goods and Services Taxpayer Identification '
                           'Number', size=15, copy=False)
    gst_type = fields.Selection(
        [('regular', 'Regular'), ('unregistered', 'Unregistered'),
         ('composite', 'Composite'), ('volunteer', 'Volunteer')],
        string='GST Type', copy=False)
    partner_location = fields.Selection(
        [('inter_state', 'Inter State'), ('intra_state', 'Intra State'),
         ('inter_country', 'Inter Country')],
        related='partner_id.partner_location', string="Partner Location")
    fiscal_position_id = fields.Many2one('account.fiscal.position',
                                         string='Nature of Transaction',
                                         oldname='fiscal_position',
                                         readonly=True,
                                         states={
                                             'draft': [('readonly', False)]})
    eway_bill_id = fields.Many2one("eway.bill", "Eway Bill", copy=False)
    picking_ids = fields.One2many(
        'stock.picking', 'invoice_id', string='Pickings')
    procurement_group_id = fields.Many2one(
        'procurement.group', 'Procurement Group', copy=False)
    picking_type_id = fields.Many2one(
        'stock.picking.type', 'Deliver To',
        states=READONLY_STATES, default=_default_picking_type, copy=False)
    dest_address_id = fields.Many2one(
        'res.partner', string='Drop Ship Address', states=READONLY_STATES)
    picking_count = fields.Integer(
        compute='_compute_picking', string='Receptions', default=0, store=True)
    delivery_count = fields.Integer(
        string='Delivery Orders', compute='_compute_picking_ids')
    all_picking_done = fields.Boolean(string="All Picking Done",
                                      compute='compute_all_done_picking')
    refund_invoice_count = fields.Integer(
        compute='_compute_refund_invoice',
        string='Credit Notes', default=0, store=True)
    partner_shipping_id = fields.Many2one(
        'res.partner', string='Delivery Address',
        readonly=True, states={'draft': [('readonly', False)]})
    warehouse_id = fields.Many2one(
        'stock.warehouse', string='Warehouse',
        required=True, readonly=True, states={'draft': [('readonly', False)]},
        default=_default_warehouse_id)
    incoterms_id = fields.Many2one(
        'stock.incoterms', string="Incoterms",
        readonly=True, states={'draft': [('readonly', False)]})

    picking_policy = fields.Selection([
        ('direct', 'Deliver each product when available'),
        ('one', 'Deliver all products at once')],
        string='Shipping Policy', required=True,
        readonly=True, default='direct',
        states={'draft': [('readonly', False)]})
    inv_type = fields.Char(string="Invoice Type")
    date_planned = fields.Datetime(
        string='Scheduled Date',
        compute='_compute_date_planned', store=True, index=True)

    @api.onchange('type', 'picking_type_id')
    def _onchange_type(self):
        for invoice in self:
            invoice.inv_type = self.type

    def compute_all_done_picking(self):
        total_quantity = 0.0
        total_pick_qty = 0.0
        all_picking_done = False
        for invoice in self:
            total_quantity = sum(
                [line.quantity for line in invoice.invoice_line_ids])
            total_pick_qty = sum([move.quantity_done for move in
                                  invoice.picking_ids.mapped('move_lines')])
            if total_quantity == total_pick_qty:
                invoice.all_picking_done = True

    @api.depends('invoice_line_ids.move_ids.returned_move_ids',
                 'invoice_line_ids.move_ids.state',
                 'invoice_line_ids.move_ids.picking_id')
    def _compute_picking(self):
        for invoice in self:
            pickings = self.env['stock.picking']
            for line in invoice.invoice_line_ids:
                moves = line.move_ids | line.move_ids.mapped(
                    'returned_move_ids')
                pickings |= moves.mapped('picking_id')
            invoice.picking_ids = pickings
            invoice.picking_count = len(pickings)

    @api.depends('picking_ids')
    def _compute_picking_ids(self):
        for invoice in self.filtered(
                lambda s: s.type in ['out_invoice', 'in_refund']):
            invoice.delivery_count = len(invoice.picking_ids)

    @api.onchange('partner_id', 'company_id')
    def _onchange_partner_id(self):
        super(AccountInvoice, self)._onchange_partner_id()
        if self.partner_id and not self.partner_id.partner_location:
            self.partner_id.partner_location = \
                self.partner_id._get_partner_location_details(self.company_id)

    @api.onchange('fiscal_position_id')
    def _onchange_fiscal_position_id(self):
        for line in self.invoice_line_ids:
            line._set_taxes()

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        if self._context.get('check_picking', False):
            picking = self._context['check_picking']
            domain = [('partner_id', '=', picking.partner_id.id),
                      ('eway_bill_id', '=', False)]
            if picking.picking_type_id.code == 'incoming':
                domain += [('type', '=', ['in_invoice', 'in_refund'])]
            elif picking.picking_type_id.code == 'outgoing':
                domain += [('type', '=', ['out_invoice',
                                          'out_refund'])]
            return self.search(domain, limit=limit).name_get()
        if self._context.get('invoice') or self._context.get(
                'invoice') == False:
            list = []
            domain = []
            invoice_ids = self.env['account.invoice'].search([])
            for invoice in invoice_ids:
                if invoice.all_picking_done:
                    list.append(invoice.id)
                domain = [('id', 'in', list), ('eway_bill_id', '=', False),
                          ('state', 'in', ['open', 'paid'])]
            return self.search(domain, limit=limit).name_get()
        return super(AccountInvoice, self).name_search(name, args, operator,
                                                       limit)

    @api.multi
    def create_picking(self):
        StockPicking = self.env['stock.picking']
        for invoice in self:
            if any([ptype in ['product', 'consu'] for ptype in invoice.
                    invoice_line_ids.mapped('product_id.type')]):
                pickings = invoice.picking_ids.filtered(
                    lambda x: x.state not in ('done', 'cancel'))
                if not pickings:
                    res = invoice._prepare_picking()
                    picking = StockPicking.create(res)
                else:
                    picking = pickings[0]
                moves = invoice.invoice_line_ids._create_stock_moves(picking)
                moves = \
                    moves.filtered(lambda x: x.state not in (
                        'done', 'cancel'))._action_confirm()
                seq = 0
                for move in sorted(moves, key=lambda move: move.date_expected):
                    seq += 5
                    move.sequence = seq
                moves._action_assign()
                picking.message_post_with_view(
                    'mail.message_origin_link',
                    values={'self': picking, 'origin': invoice},
                    subtype_id=self.env.ref('mail.mt_note').id)
        return True

    @api.model
    def _prepare_picking(self):
        if not self.procurement_group_id:
            self.procurement_group_id = self.procurement_group_id.create({
                'name': self.number,
                'partner_id': self.partner_id.id
            })
        if not self.partner_id.property_stock_supplier.id:
            raise UserError(_("You must set a Vendor Location for this "
                              "partner %s") % self.partner_id.name)
        return {
            'picking_type_id': self.picking_type_id.id,
            'partner_id': self.partner_id.id,
            'date': self.date_invoice,
            'origin': self.number,
            'location_dest_id': self._get_destination_location(),
            'location_id': self.partner_id.property_stock_customer.id,
            'company_id': self.company_id.id,
            'invoice_id': self.id
        }

    @api.multi
    def _get_destination_location(self):
        self.ensure_one()
        if self.partner_id:
            return self.partner_id.property_stock_customer.id
        return self.picking_type_id.default_location_dest_id.id

    @api.multi
    def action_view_delivery_or_picking(self):
        if self.type in ['out_invoice', 'in_refund']:
            action = self.env.ref('stock.action_picking_tree_all').read()[0]
        elif self.type in ['in_invoice', 'out_refund']:
            action = self.env.ref('stock.action_picking_tree').read()[0]
            action['context'] = {}
        pickings = self.mapped('picking_ids')
        if len(pickings) > 1:
            action['domain'] = [('id', 'in', pickings.ids)]
        elif pickings:
            action['views'] = [(
                self.env.ref('stock.view_picking_form').id, 'form')]
            action['res_id'] = pickings.id
        return action

    @api.multi
    def action_move_create(self):
        """ Do not apply taxes if company has been registered under
        composition scheme. """
        for invoice in self.filtered(lambda l: l.type in [
            'out_invoice',  'out_refund'] and l.company_id.gst_type ==
                                               'composite'):
            for line in invoice.invoice_line_ids:
                line.invoice_line_tax_ids = [(6, 0, [])]
                line.invoice_id._onchange_invoice_line_ids()
        return super(AccountInvoice, self).action_move_create()

    @api.multi
    def invoice_validate(self):
        """ Apply GST invoice type at the time of invoice validation. """
        for invoice in self:
            partner_location = self.partner_id.partner_location
            if invoice.partner_id.vat:
                invoice.write({
                    'vat': invoice.partner_id.vat,
                    'gst_type': invoice.partner_id.gst_type,
                    'gst_invoice': 'b2b'
                })
            elif invoice.type == 'out_invoice' and partner_location:
                # b2c_limit = self.env['res.company.b2c.limit'].search(
                #     [('date_from', '<=', invoice.date_invoice),
                #      ('date_to', '>=', invoice.date_invoice),
                #      ('company_id', '=', invoice.company_id.id)])
                # if not b2c_limit:
                #     raise ValidationError(_('Please define B2C limit line in '
                #                             'company for current period!'))
                if partner_location == 'inter_state':
                    invoice.write({'gst_invoice': 'b2cl'})
                if partner_location == 'intra_state':
                    invoice.write({'gst_invoice': 'b2cs'})
            elif invoice.type == 'in_invoice' and partner_location and \
                    partner_location != 'inter_country':
                invoice.write({'gst_invoice': 'b2bur'})

        return super(AccountInvoice, self).invoice_validate()

    @api.model
    def _prepare_refund(self, invoice, date_invoice=None, date=None,
                        description=None, journal_id=None):
        """ Refund invoice creation, update value of GST Invoice from
        base invoice. """
        result = super(AccountInvoice, self)._prepare_refund(
            invoice, date_invoice=date_invoice, date=date,
            description=description, journal_id=journal_id)
        if result.get('refund_invoice_id'):
            invoice = self.env['account.invoice'].browse(
                result.get('refund_invoice_id'))
            result.update({
                'gst_invoice': invoice.gst_invoice, 'vat': invoice.vat,
                'gst_type': invoice.gst_type,
            })
        return result

    def _get_total_tax_detail(self):
        bill_lines = []
        cess_amount = igst_amount = cgst_amount = sgst_amount = cess_rate = \
            igst_rate = cgst_rate = sgst_rate = 0.0
        acc_tax = self.env['account.tax']
        for line in self.invoice_line_ids:
            cess_rate = igst_rate = cgst_rate = sgst_rate = 0.0
            price_unit = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
            taxes = line.invoice_line_tax_ids.compute_all(
                price_unit, line.invoice_id.currency_id, line.quantity,
                line.product_id, line.invoice_id.partner_id)['taxes']
            total_tax_amount = []
            for tax_id in taxes:
                tax = acc_tax.browse(tax_id['id'])
                total_tax_amount.append(str(tax['amount']))
                if tax.tax_group_id.name == 'Cess':
                    cess_rate += tax['amount']
                    cess_amount += tax_id['amount']
                elif tax.tax_group_id.name == 'IGST':
                    igst_rate += tax['amount']
                    igst_amount += tax_id['amount']
                elif tax.tax_group_id.name == 'CGST':
                    cgst_rate += tax['amount']
                    cgst_amount += tax_id['amount']
                elif tax.tax_group_id.name == 'SGST':
                    sgst_rate += tax['amount']
                    sgst_amount += tax_id['amount']
            total_tax = '+'.join(total_tax_amount)
            bill_lines.append((0, 0, {
                'product_id': line.product_id.id,
                'product_desc': line.name,
                'hsn_code': line.product_id.l10n_in_hsn_code,
                'uom_id': line.uom_id and line.uom_id.id or False,
                'qty': line.quantity,
                'asseseble_value': line.price_subtotal,
                'total_tax_amount': total_tax or 0.0, 'cgst_rate': cgst_rate,
                'sgst_rate': sgst_rate, 'igst_rate': igst_rate,
                'cess_rate': cess_rate
            }))
        return bill_lines, cgst_amount, sgst_amount, igst_amount, cess_amount


class AccountInvoiceLine(models.Model):
    _inherit = 'account.invoice.line'

    route_id = fields.Many2one(
        'stock.location.route', string='Route',
        domain=[('invoice_selectable', '=', True)], ondelete='restrict')

    move_ids = fields.One2many(
        'stock.move', 'invoice_line_id', string='Stock Moves')
    qty_delivered_updateable = fields.Boolean('Delivered?')
    qty_delivered = fields.Float(
        compute='_compute_qty_delivered',
        string='Delivered', copy=False,
        digits=dp.get_precision('Product Unit of Measure'), store=True)
    date_planned = fields.Datetime(
        string='Scheduled Date', index=True, default=fields.Date.context_today)
    move_dest_ids = fields.One2many(
        'stock.move', 'created_invoice_line_id', 'Downstream Moves')
    qty_received = fields.Float(
        compute='_compute_qty_received',
        string="Received Qty",
        digits=dp.get_precision('Product Unit of Measure'),
        store=True)

    @api.depends('invoice_id.state', 'move_ids.state',
                 'move_ids.product_uom_qty')
    def _compute_qty_received(self):
        for line in self:
            total = 0.0
            for move in line.move_ids.filtered(
                    lambda l: l.state == 'done' and l.to_refund):
                if move.location_dest_id.usage == "supplier":
                    total -= move.product_uom._compute_quantity(
                        move.product_uom_qty, line.uom_id)
                else:
                    total += move.product_uom._compute_quantity(
                        move.product_uom_qty, line.uom_id)
            line.qty_received = total

    @api.onchange('product_id')
    def _onchange_product_id_uom_check_availability(self):
        if not self.uom_id or (
                self.product_id.uom_id.category_id.id !=
                self.uom_id.category_id.id):
            self.uom_id = self.product_id.uom_id
        self.customer_lead = self.product_id.sale_delay
        self._onchange_product_id_check_availability()

    @api.onchange('quantity', 'uom_id', 'route_id')
    def _onchange_product_id_check_availability(self):
        if not self.product_id or not self.quantity or not \
                self.uom_id or not \
                self.invoice_id:
            return {}
        date_invoice = self.invoice_id.date_invoice
        seller = self.product_id._select_seller(
            partner_id=self.partner_id,
            quantity=self.quantity,
            date=date_invoice and date_invoice[:10],
            uom_id=self.uom_id)

        if seller or not self.date_planned:
            self.date_planned = \
                self._get_date_planned(seller).strftime('%Y-%m-%d')

        if self.product_id.type == 'product':
            precision = self.env['decimal.precision'].precision_get(
                'Product Unit of Measure')
            product = self.product_id.with_context(
                warehouse=self.invoice_id.warehouse_id.id)
            product_qty = self.uom_id._compute_quantity(
                self.quantity, self.product_id.uom_id)
            if float_compare(product.virtual_available, product_qty,
                             precision_digits=precision) == -1:
                is_available = self._check_routing()
                if not is_available and self.invoice_id.type \
                        in ['out_invoice', 'in_refund']:
                    message = _('You plan to invoice %s %s but you only '
                                'have %s %s available in %s warehouse.') % (
                                  self.quantity, self.uom_id.name,
                                  product.virtual_available,
                                  product.uom_id.name,
                                  self.invoice_id.warehouse_id.name)
                    if float_compare(product.virtual_available,
                                     self.product_id.virtual_available,
                                     precision_digits=precision) == -1:
                        message += _('\nThere are %s %s available accross all'
                                     ' warehouses.') % (
                                       self.product_id.virtual_available,
                                       product.uom_id.name)

                    warning_mess = {
                        'title': _('Not enough inventory!'),
                        'message': message
                    }
                    return {'warning': warning_mess}
        return {}

    @api.model
    def _get_date_planned(self, seller, invoice=False):
        date = invoice.date_invoice if invoice \
            else self.invoice_id.date_invoice
        if date:
            return datetime.strptime(date, '%Y-%m-%d') + relativedelta(
                days=seller.delay if seller else 0)
        else:
            return datetime.today() + relativedelta(
                days=seller.delay if seller else 0)

    @api.multi
    def action_invoice_cancel(self):
        self.mapped('picking_ids').action_cancel()
        return super(AccountInvoice, self).action_invoice_cancel()

    @api.multi
    def action_invoice_open(self):
        self.check_quantity()
        self.check_duplicate_product()
        super(AccountInvoice, self).action_invoice_open()
        for invoice in self:
            if invoice.type in ['out_invoice', 'in_refund']:
                invoice.invoice_line_ids._action_launch_procurement_rule()
            elif invoice.type in ['in_invoice', 'out_refund']:
                invoice._add_supplier_to_product()
                invoice._create_picking()

    @api.multi
    def _prepare_procurement_values(self, group_id=False):
        self.ensure_one()
        date_planned = datetime.strptime(
            self.invoice_id.date_invoice, '%Y-%m-%d') + timedelta(
            days=self.customer_lead or 0.0) - timedelta(
            days=self.invoice_id.company_id.security_lead)
        return {
            'company_id': self.invoice_id.company_id,
            'group_id': group_id,
            'invoice_line_id': self.id,
            'date_planned':
                date_planned.strftime(DEFAULT_SERVER_DATETIME_FORMAT),
            'route_ids': self.route_id,
            'warehouse_id': self.invoice_id.warehouse_id or False,
            'partner_dest_id': self.invoice_id.partner_shipping_id
        }

    @api.multi
    def _action_launch_procurement_rule(self):
        precision = self.env['decimal.precision'].precision_get(
            'Product Unit of Measure')
        errors = []
        for line in self:
            if line.state != 'open' or line.product_id.type not in (
                    'consu', 'product'):
                continue
            qty = 0.0
            for move in line.move_ids.filtered(lambda r: r.state != 'cancel'):
                qty += move.product_uom._compute_quantity(
                    move.product_uom_qty, line.uom_id,
                    rounding_method='HALF-UP')
            if float_compare(
                    qty, line.quantity, precision_digits=precision) >= 0:
                continue

            group_id = line.invoice_id.procurement_group_id
            if not group_id:
                group_id = self.env['procurement.group'].create({
                    'name': line.invoice_id.number,
                    'move_type': line.invoice_id.picking_policy,
                    'invoice_id': line.invoice_id.id,
                    'partner_id': line.invoice_id.partner_shipping_id.id,
                })
                line.invoice_id.procurement_group_id = group_id
            else:
                updated_vals = {}
                if group_id.partner_id != line.invoice_id.partner_shipping_id:
                    updated_vals.update({
                        'partner_id': line.invoice_id.partner_shipping_id.id})
                if group_id.move_type != line.invoice_id.picking_policy:
                    updated_vals.update({
                        'move_type': line.invoice_id.picking_policy})
                if updated_vals:
                    group_id.write(updated_vals)

            values = line._prepare_procurement_values(group_id=group_id)
            product_qty = line.quantity - qty

            procurement_uom = line.uom_id
            quant_uom = line.product_id.uom_id
            get_param = self.env['ir.config_parameter'].sudo().get_param
            if procurement_uom.id != quant_uom.id and get_param(
                    'stock.propagate_uom') != '1':
                product_qty = line.uom_id._compute_quantity(
                    product_qty, quant_uom, rounding_method='HALF-UP')
                procurement_uom = quant_uom
            try:
                partner_shipping_id = line.invoice_id.partner_shipping_id
                self.env['procurement.group'].run(
                    line.product_id, product_qty, procurement_uom,
                    partner_shipping_id.property_stock_customer, line.name,
                    line.invoice_id.number, values)
            except UserError as error:
                errors.append(error.name)
        if errors:
            raise UserError('\n'.join(errors))
        return True

    @api.multi
    @api.depends('invoice_id.state', 'move_ids.state',
                 'move_ids.product_uom_qty')
    def _compute_qty_delivered(self):
        for line in self:
            qty = 0.0
            for move in line.move_ids.filtered(
                    lambda r: r.state == 'done' and not r.scrapped):
                if move.location_dest_id.usage == "customer":
                    if not move.origin_returned_move_id:
                        qty += move.product_uom._compute_quantity(
                            move.product_uom_qty, line.uom_id)
                elif move.location_dest_id.usage != "customer" and  \
                        move.to_refund:
                    qty -= move.product_uom._compute_quantity(
                        move.product_uom_qty, line.uom_id)
            line.qty_delivered = qty

    def _check_routing(self):
        is_available = False
        product_routes = \
            self.route_id or (
                    self.product_id.route_ids +
                    self.product_id.categ_id.total_route_ids)
        wh_mto_route = self.invoice_id.warehouse_id.mto_pull_id.route_id
        if wh_mto_route and wh_mto_route <= product_routes:
            is_available = True
        else:
            mto_route = False
            try:
                mto_route = self.env['stock.warehouse']._get_mto_route()
            except UserError:
                pass
            if mto_route and mto_route in product_routes:
                is_available = True
        if not is_available:
            for pull_rule in product_routes.mapped('pull_ids'):
                if pull_rule.picking_type_id.sudo().default_location_src_id. \
                        usage == 'supplier' and pull_rule.picking_type_id. \
                        sudo().default_location_dest_id.usage == 'customer':
                    is_available = True
                    break
        return is_available

    @api.multi
    def _create_stock_moves(self, picking):
        moves = self.env['stock.move']
        done = self.env['stock.move'].browse()
        for line in self:
            for val in line._prepare_stock_moves(picking):
                done += moves.create(val)
        return done

    @api.multi
    def _prepare_stock_moves(self, picking):
        self.ensure_one()
        res = []
        if self.product_id.type not in ['product', 'consu']:
            return res
        qty = 0.0
        price_unit = self._get_stock_move_price_unit()
        for move in self.move_ids.filtered(
                lambda x: x.state != 'cancel' and
                          not x.location_dest_id.usage == "supplier"):
            qty += move.product_uom._compute_quantity(
                move.product_uom_qty, self.uom_id,
                rounding_method='HALF-UP')
        route_ids = self.invoice_id.picking_type_id.warehouse_id.route_ids
        template = {
            'name': self.name or '',
            'product_id': self.product_id.id,
            'product_uom': self.uom_id.id,
            'date': self.invoice_id.date_invoice,
            'date_expected': self.date_planned or self.invoice_id.date_invoice,
            'location_id':
                self.invoice_id.partner_id.property_stock_supplier.id,
            'location_dest_id': self.invoice_id._get_destination_location(),
            'picking_id': picking.id,
            'partner_id': self.invoice_id.dest_address_id.id,
            'move_dest_ids': [(4, x) for x in self.move_dest_ids.ids],
            'state': 'draft',
            'invoice_line_id': self.id,
            'company_id': self.invoice_id.company_id.id,
            'price_unit': price_unit,
            'picking_type_id': self.invoice_id.picking_type_id.id,
            'group_id': self.invoice_id.procurement_group_id.id,
            'origin': self.invoice_id.name,
            'route_ids':
                self.invoice_id.picking_type_id.warehouse_id and [
                    (6, 0, [x.id for x in route_ids])] or [],
            'warehouse_id': self.invoice_id.picking_type_id.warehouse_id.id,
        }
        diff_quantity = self.quantity - qty
        if float_compare(diff_quantity, 0.0,
                         precision_rounding=self.uom_id.rounding) > 0:
            quant_uom = self.product_id.uom_id
            get_param = self.env['ir.config_parameter'].sudo().get_param
            if self.uom_id.id != quant_uom.id and get_param(
                    'stock.propagate_uom') != '1':
                product_qty = self.uom_id._compute_quantity(
                    diff_quantity, quant_uom, rounding_method='HALF-UP')
                template['product_uom'] = quant_uom.id
                template['product_uom_qty'] = product_qty
            else:
                template['product_uom_qty'] = diff_quantity
            res.append(template)
        return res

    @api.multi
    def _get_stock_move_price_unit(self):
        self.ensure_one()
        line = self[0]
        invoice = line.invoice_id
        price_unit = line.price_unit
        if line.invoice_line_tax_ids:
            price_unit = line.invoice_line_tax_ids.with_context(
                round=False).compute_all(
                price_unit, currency=line.invoice_id.currency_id,
                quantity=1.0, product=line.product_id,
                partner=line.invoice_id.partner_id
            )['total_excluded']
        if line.uom_id.id != line.product_id.uom_id.id:
            price_unit *= line.uom_id.factor / line.product_id.uom_id.factor
        if invoice.currency_id != invoice.company_id.currency_id:
            price_unit = invoice.currency_id.compute(
                price_unit, invoice.company_id.currency_id, round=False)
        return price_unit
