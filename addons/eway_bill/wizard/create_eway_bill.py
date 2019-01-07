from flectra import api, fields, models, _
from flectra.exceptions import ValidationError


class GenerateEwayBill(models.TransientModel):
    _name = "generate.eway.bill"

    sub_type_id = fields.Many2one("sub.type", "Sub Type", required=True)
    order_count = fields.Integer("Order Count")
    invoice_id = fields.Many2one("account.invoice", "Invoice")
    picking_ids = fields.Many2many('stock.picking', string="Delivery/Receipt")
    picking_id = fields.Many2one("stock.picking", "Delivery/Receipt")
    order_ids = fields.One2many("generate.eway.bill.line", 'wizard_id',
                                'Order Lines')

    def check_eway_exist(self, model, order):
        order = self.env[model].browse(order)
        name = order.number if model == "account.invoice" else order.name
        if order.eway_bill_id and name:
            raise ValidationError(_(
                "Eway Bill is already created for %s" % name))

    @api.onchange('invoice_id')
    def onchange_invoice_id(self):
        if self.invoice_id and self.invoice_id.picking_ids:
            self.picking_ids = self.invoice_id.picking_ids
            return {'domain': {'picking_ids': [
                ('id', 'in', self.invoice_id.picking_ids.ids)]}}

    @api.model
    def default_get(self, fields):
        defaults = super(GenerateEwayBill, self).default_get(fields)
        model = self.env.context.get("active_model", False)
        active_ids = self.env.context.get("active_ids", False)
        order_count = len(active_ids)
        key = 'picking_id' if model == 'stock.picking' else 'invoice_id'
        defaults.update({'order_count': order_count})
        if order_count == 1:
            self.check_eway_exist(model, active_ids[0])
            defaults.update({key: active_ids[0]})
            if self.env[model].browse(active_ids).picking_ids:
                defaults.update({'picking_ids': [
                    (6, 0, self.env[model].browse(active_ids).picking_ids.ids)
                ]})
        elif order_count > 1:
            final_list = []
            for order in active_ids:
                self.check_eway_exist(model, order)
                final_list.append((0, False, {key: order}))
                if self.browse(order).picking_ids:
                    defaults.update({'picking_ids': [
                        (6, 0, self.browse(order).picking_ids.ids)]})
            defaults.update({'order_ids': final_list})
        return defaults

    @api.multi
    def create_eway_bill(self, invoice, picking_ids):
        model = self.env.context.get("active_model", False)
        active_ids = self.env.context.get("active_ids", False)
        trans_mode = False
        trans_partner_id = False
        trans_id = False
        trans_doc_number = False
        trans_doc_date = False
        vehicle_no = False
        vehicle_type = False
        for picking in picking_ids:
            trans_mode = picking.trans_mode or False
            trans_partner_id = \
                picking.trans_partner_id and \
                picking.trans_partner_id.id or False
            trans_id = picking.trans_id
            trans_doc_number = picking.trans_doc_number
            trans_doc_date = picking.trans_doc_date
            vehicle_no = picking.vehicle_no
            vehicle_type = picking.vehicle_type
        company_partner_id = self.env.user.company_id.partner_id
        supply_type = 'I' if invoice.type in ['in_invoice',
                                              'out_refund'] else (
            'O' if invoice.type in ['out_invoice', 'in_refund'] else False)
        doc_type = 'INV' if invoice.type == 'out_invoice' else (
            'BIL' if invoice.type == 'in_invoice' else (
                'CNT' if invoice.type in ['in_refund', 'out_refund']
                else 'OTH'))
        doc_date = invoice.date_invoice
        bill_lines, cgst_amount, sgst_amount, igst_amount, cess_amount = \
            invoice._get_total_tax_detail()
        eway_bill_data = {
            'supply_type': supply_type,
            'sub_type_id': self.sub_type_id and self.sub_type_id.id or False,
            'invoice_type': doc_type, 'doc_date': doc_date,
            'invoice_id': invoice.id,
            'from_partner_id': invoice.partner_id.id,
            'picking_ids': [(6, 0, picking_ids.ids)] or False,
            'eway_product_lines': bill_lines,
            'trans_mode': trans_mode,
            'trans_partner_id': trans_partner_id,
            'trans_id': trans_id,
            'trans_doc_number': trans_doc_number,
            'trans_doc_date': trans_doc_date,
            'vehicle_no': vehicle_no,
            'vehicle_type': vehicle_type,
            'amount_total': invoice.amount_total,
            'cgst_amount': cgst_amount,
            'sgst_amount': sgst_amount,
            'igst_amount': igst_amount,
            'cess_amount': cess_amount
        }
        if invoice.type in ['in_invoice', 'in_refund']:
            eway_bill_data.update({
                'from_partner_id': picking.partner_id and
                                   picking.partner_id.id or False,
                'to_partner_id': company_partner_id.id
            })
        elif invoice.type in ['out_invoice', 'out_refund']:
            eway_bill_data.update({
                'to_partner_id':
                    invoice.partner_id and invoice.partner_id.id or False,
                'from_partner_id': company_partner_id.id
            })
        eway_bill = self.env['eway.bill'].create(eway_bill_data)
        invoice.eway_bill_id = eway_bill
        for picking in picking_ids:
            picking.eway_bill_id = eway_bill
        return eway_bill.id

    def generate_eway(self):
        if self.order_count == 0:
            raise ValidationError(_("Select atleast one Invoice/Picking to "
                                    "generate eway bill!"))
        action = {
            'name': _("Eway Bill"),
            'type': 'ir.actions.act_window',
            'res_model': 'eway.bill',
        }
        if self.order_count == 1:
            eway_bill = self.create_eway_bill(self.invoice_id,
                                              self.picking_ids)
            action.update({'view_mode': 'form', 'res_id': eway_bill})
        elif self.order_count > 1 and self.order_ids:
            eway_bill = []
            for order in self.order_ids:
                eway_bill.append(self.create_eway_bill(order.invoice_id,
                                                       order.picking_ids))
            action.update({'view_mode': 'tree,form',
                           'domain': [('id', 'in', eway_bill)]})
        return action


class GenerateEwayBillLine(models.TransientModel):
    _name = "generate.eway.bill.line"

    wizard_id = fields.Many2one("generate.eway.bill", "Wizard")
    picking_ids = fields.Many2many('stock.picking', string="Delivery/Receipt")
    invoice_id = fields.Many2one("account.invoice", "Invoice")
