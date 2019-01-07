# Part of Flectra See LICENSE file for full copyright and licensing details.

from flectra import api, fields, models, _
from flectra.exceptions import ValidationError


class SubType(models.Model):
    _name = "sub.type"

    name = fields.Char("Name", required=True)
    code = fields.Char("Code", required=True)


class EWayBill(models.Model):
    _name = 'eway.bill'

    name = fields.Char('Name', default='/')
    ewayno = fields.Char("Eway Bill Number")
    supply_type = fields.Selection([('I', 'Inward'),
                                    ('O', 'Outward')], "Supply Type",
                                   required=True)
    sub_type_id = fields.Many2one('sub.type', "Sub Type", required=False)
    invoice_id = fields.Many2one('account.invoice', 'Invoice')
    picking_id = fields.Many2one('stock.picking', string='Reference')
    picking_ids = fields.Many2many('stock.picking', string='References')
    invoice_type = fields.Selection([
        ('INV', 'Tax Invoice'),
        ('BIL', 'Bill of Supply'),
        ('BOE', 'Bill of Entry'),
        ('CHL', 'Delivery Challan'),
        ('CNT', 'Credit Note'),
        ('OTH', 'Others'),
    ], "Doc Type", required=True)
    trans_mode = fields.Selection([
        ('1', 'Road'),
        ('2', 'Rail'),
        ('3', 'Air'),
        ('4', 'Ship'),
    ], "Trans Mode", required=True, default='1')
    doc_date = fields.Date("Doc Date")
    from_partner_id = fields.Many2one("res.partner", "From other party "
                                                     "name", required=True)

    dispatch_state = fields.Many2one("res.country.state", 'Dispatch State',
                                     related='from_partner_id.state_id')
    to_partner_id = fields.Many2one("res.partner", "To other party name")

    ship_to_state = fields.Many2one("res.country.state", 'Ship to State',
                                    required=False)
    eway_product_lines = fields.One2many("eway.bill.line", 'eway_bill_id',
                                         'E-Way Bill Lines')
    distance = fields.Float("Distance(km)", required=False)
    trans_partner_id = fields.Many2one("res.partner", "Transporter Name")
    trans_id = fields.Char("Transporter ID",
                           related='trans_partner_id.trans_id', store=True)
    trans_doc_number = fields.Char("Trans Document Number")
    trans_doc_date = fields.Date("Transporter Doc Date")
    vehicle_no = fields.Char("Vehicle No")
    vehicle_type = fields.Selection("Vehicle Type",
                                    related="picking_id.vehicle_type")
    amount_total = fields.Float("Total Amount")
    cgst_amount = fields.Float("CGST Amount")
    sgst_amount = fields.Float("SGST Amount")
    igst_amount = fields.Float("IGST Amount")
    cess_amount = fields.Float("CESS Amount")
    state = fields.Selection([('draft', 'Draft'), ('confirm', 'Confirm'),
                              ('done', 'Done'), ('cancel', 'Cancelled')],
                             'Status', default='draft')

    @api.model
    def create(self, vals):
        if not vals.get('name') or vals['name'] == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code(
                'eway.bill') or _('New')
        return super(EWayBill, self).create(vals)

    @api.onchange('invoice_id')
    def onchange_invoice_id(self):
        self.picking_ids = []
        company_partner_id = self.env.user.company_id.partner_id
        bill_lines, cgst_amount, sgst_amount, igst_amount, cess_amount = \
            self.invoice_id._get_total_tax_detail()
        if self.invoice_id:
            for picking in self.invoice_id:
                picking.eway_bill_id = self.id
            doc_type = 'INV' if self.invoice_id.type == 'out_invoice' else (
                'BIL' if self.invoice_id.type == 'in_invoice' else (
                    'CNT' if self.invoice_id.type in ['in_refund',
                                                      'out_refund']
                    else 'OTH'))
            self.doc_date = self.invoice_id.date_invoice
            self.picking_ids = [(6, 0,
                                 self.invoice_id.picking_ids.ids)] or False
            self.supply_type = 'I' if self.invoice_id.type in [
                'in_invoice', 'out_refund'] else (
                'O' if self.invoice_id.type in ['out_invoice',
                                                'in_refund'] else False)
            self.sub_type_id = self.env['sub.type'].search([('code', '=', 1)])
            picking = self.env['stock.picking'].search(
                [('id', 'in', self.invoice_id.picking_ids.ids)], limit=1)
            if self.invoice_id.type in ['in_invoice', 'in_refund']:
                self.from_partner_id = picking.partner_id and \
                                       picking.partner_id.id or False,
                self.to_partner_id = company_partner_id.id
            elif self.invoice_id.type in ['out_invoice', 'out_refund']:
                self.to_partner_id = self.invoice_id.partner_id and \
                                     self.invoice_id.partner_id.id or False,
                self.from_partner_id = company_partner_id.id

            self.trans_mode = picking.trans_mode or False
            self.trans_partner_id = \
                picking.trans_partner_id and picking.trans_partner_id.id or \
                False
            self.trans_id = picking.trans_id
            self.trans_doc_number = picking.trans_doc_number
            self.trans_doc_date = picking.trans_doc_date
            self.vehicle_no = picking.vehicle_no
            self.vehicle_type = picking.vehicle_type
            self.eway_product_lines = bill_lines
            self.invoice_type = doc_type
            self.invoice_id = self.invoice_id.id
            self.amount_total = self.invoice_id.amount_total
            self.cgst_amount = cgst_amount
            self.sgst_amount = sgst_amount
            self.igst_amount = igst_amount
            self.cess_amount = cess_amount
            return {'domain': {'picking_ids': [
                ('id', 'in', self.invoice_id.picking_ids.ids)]}}

    def action_confirm(self):
        invoice_id = self.search([('invoice_id', '=', self.invoice_id.id),
                                  ('state', 'in', ['confirm', 'done'])])
        if invoice_id:
            raise ValidationError(
                _('Error ! Eway bill already created for this invoice'))
        elif not self.invoice_id.all_picking_done:
            raise ValidationError(
                _('Error ! Please Transfer all the invoiced quantities'))
        else:
            self.invoice_id.eway_bill_id = self.id
        self.state = 'confirm'

    def action_done(self):
        self.state = 'done'

    def action_cancel(self):
        self.state = 'cancel'

    def set_to_draft(self):
        self.state = 'draft'


class EWayBillLine(models.Model):
    _name = 'eway.bill.line'

    eway_bill_id = fields.Many2one("eway.bill", 'Eway Bill')
    product_id = fields.Many2one("product.product", 'Product', required=True)
    product_desc = fields.Char("Description")
    hsn_code = fields.Char("HSN Code",
                           related='product_id.l10n_in_hsn_code', store=True)
    uom_id = fields.Many2one("product.uom", "UNIT")
    qty = fields.Float("Quantity", required=True)
    asseseble_value = fields.Float("Asseseble Value", required=True)
    total_tax_amount = fields.Char("Tax Rate(C+S+I+Cess)")
    cgst_rate = fields.Float("CGST Rate")
    sgst_rate = fields.Float("SGST Rate")
    igst_rate = fields.Float("IGST Rate")
    cess_rate = fields.Float("CESS Rate")
