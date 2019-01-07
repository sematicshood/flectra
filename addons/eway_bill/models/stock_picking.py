# Part of Flectra See LICENSE file for full copyright and licensing details.

from flectra import api, fields, models, _
from flectra.exceptions import UserError
from flectra.tools.misc import formatLang


class StockPicking(models.Model):
    _inherit = "stock.picking"

    trans_mode = fields.Selection(
        [('1', 'Road'), ('2', 'Rail'), ('3', 'Air'),
         ('4', 'Ship'), ], "Trans Mode", required=True,
        default='1')
    distance = fields.Float("Distance(km)", required=False)
    trans_partner_id = fields.Many2one("res.partner", "Transporter Name")
    trans_id = fields.Char("Trasporter ID")
    trans_doc_number = fields.Char("Trans Document Number")
    trans_doc_date = fields.Date("Transporter Doc Date")
    vehicle_no = fields.Char("Vehicle Number")
    vehicle_type = fields.Selection([('reg', 'Regular'), ('odc', 'ODC')],
                                    "Vehicle Type", default='reg')
    generated_from_invoice = fields.Boolean(_compute='_generated_from_invoice')
    eway_bill_id = fields.Many2one("eway.bill", "Eway Bill")
    invoice_id = fields.Many2one(
        related='move_lines.invoice_line_id.invoice_id',
        string="Invoice", readonly=True)

    @api.onchange('picking_type_id', 'partner_id')
    def onchange_picking_type(self):
        if self.partner_id and self.partner_id.transporter_id:
            self.trans_partner_id = self.partner_id.transporter_id
            self.trans_id = self.partner_id.trans_id

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        if self._context.get('check_invoice', False):
            invoice = self.env["account.invoice"].browse(
                self._context['check_invoice'])
            domain = [('partner_id', '=', invoice.partner_id.id),
                      ('eway_bill_id', '=', False)]
            if invoice.type in ['in_invoice', 'in_refund']:
                domain += [('picking_type_id.code', '=', 'incoming')]
            else:
                domain += [('picking_type_id.code', '=', 'outgoing')]
            return self.search(domain, limit=limit).name_get()
        return super(StockPicking, self).name_search(name, args, operator,
                                                     limit)

    @api.model
    def create(self, vals):
        if vals.get('partner_id', False):
            partner = self.env['res.partner'].browse(vals['partner_id'])
            vals['trans_partner_id'] = partner.transporter_id and \
                                       partner.transporter_id.id or False
            vals['trans_id'] = partner.trans_id
        return super(StockPicking, self).create(vals)

    @api.multi
    def check_quantity(self):
        for picking in self:
            data_dict = \
                picking.invoice_id.get_quantity_update(picking.invoice_id)
            if not data_dict:
                return
            msg = 'Following Quantity is greater' \
                  ' than remaining qtyuantity!\n'
            check_warning = False
            for line in picking.move_lines:
                if self.invoice_id.type == 'out_refund':
                    qty = sum(
                        [original_line.qty_delivered for original_line in
                         self.invoice_id.refund_invoice_id.invoice_line_ids
                         if line.product_id == original_line.product_id])
                if data_dict:
                    remaining_qty = qty - data_dict.get(
                        line.product_id.id).get('quantity')
                else:
                    remaining_qty = qty
                if line.product_uom_qty > remaining_qty:
                    check_warning = True
                    msg += ("\n Product (%s) => Quantity (%s) should be "
                            "less than remaining quantity (%s)!") % (
                               line.product_id.name,
                               formatLang(self.env, line.product_uom_qty,
                                          digits=2),
                               formatLang(self.env, remaining_qty, digits=2))
            if check_warning:
                raise UserError(_(msg))

    @api.multi
    def action_assign(self):
        res = super(StockPicking, self).action_assign()
        if self.invoice_id:
            self.check_quantity()
        return res

    @api.multi
    def button_validate(self):
        res = super(StockPicking, self).button_validate()
        if self.invoice_id:
            self.check_quantity()
        return res


class StockMove(models.Model):
    _inherit = "stock.move"

    invoice_line_id = fields.Many2one('account.invoice.line', 'Invoice Line')
    created_invoice_line_id = fields.Many2one(
        'account.invoice.line', 'Created Invoice Line',
        ondelete='set null', readonly=True, copy=False)
