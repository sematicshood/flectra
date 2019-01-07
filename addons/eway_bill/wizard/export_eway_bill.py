# Part of Flectra See LICENSE file for full copyright and licensing details.

import base64
import json

from flectra import fields, models, _


class ExportEwayBill(models.TransientModel):
    _name = "export.eway.bill"

    def _get_filename(self):
        active_id = self.env.context.get("active_id", False)
        eway_bill = self.env["eway.bill"].browse(active_id)
        return 'EwayBill-' + str(eway_bill.id) + '.json'

    file = fields.Binary("Eway Bill Json File", attachment=True)
    filename = fields.Char("Filename", default=_get_filename)

    def generate_eway_bill(self):
        active_id = self.env.context.get("active_id", False)
        eway_bill = self.env["eway.bill"].browse(active_id)
        from_patrner = eway_bill.from_partner_id
        to_partner = eway_bill.to_partner_id
        data_store = {"version": "1.0.0123",
                      "billLists": []}
        data = {"genMode": "Excel",
                "userGstin": self.env.user.company_id.vat,
                "supplyType": eway_bill.supply_type,
                "subSupplyType": eway_bill.sub_type_id and
                                 eway_bill.sub_type_id.name or '',
                "docType": eway_bill.invoice_type,
                "docNo": eway_bill.invoice_type,
                "docDate": eway_bill.doc_date,
                "transMode": eway_bill.trans_mode,
                "transDistance": eway_bill.distance,
                "transporterName": eway_bill.trans_partner_id and
                                   eway_bill.trans_partner_id.name or '',
                "transporterId": eway_bill.trans_partner_id and
                                 eway_bill.trans_partner_id.trans_id or '',
                "transDocNo": eway_bill.trans_doc_number,
                "transDocDate": eway_bill.trans_doc_date,
                "totalValue": eway_bill.amount_total,
                "vehicleNo": eway_bill.vehicle_no,
                "cgstValue": eway_bill.cgst_amount,
                "sgstValue": eway_bill.sgst_amount,
                "igstValue": eway_bill.igst_amount,
                "cessValue": eway_bill.cess_amount,
                }
        if from_patrner:
            data.update({
                "fromGstin": from_patrner and from_patrner.vat or 'URP',
                "fromTrdName": from_patrner.name,
                "fromAddr1": from_patrner.street,
                "fromAddr2": from_patrner.street2,
                "fromPlace": from_patrner.city,
                "fromPincode": from_patrner.zip,
                "fromStateCode": from_patrner.state_id and
                                 from_patrner.state_id.code or '',
            })
        if to_partner:
            data.update({
                "toGstin": to_partner and to_partner.vat or 'URP',
                "toTrdName": to_partner.name,
                "toAddr1": to_partner.street,
                "toAddr2": to_partner.street2,
                "toPlace": to_partner.city,
                "toPincode": to_partner.zip,
                "toStateCode": to_partner.state_id.code,
            })
        if eway_bill.eway_product_lines:
            count = 0
            lines = []
            for line in eway_bill.eway_product_lines:
                count += 1
                lines.append({
                    "itemNo": count,
                    "productName": line.product_id and line.product_id.name
                                   or '',
                    "productDesc": line.product_desc,
                    "hsnCode": line.product_id and
                               line.product_id.l10n_in_hsn_code or '',
                    "quantity": line.qty,
                    "qtyUnit": line.uom_id and line.uom_id.name or '',
                    "taxableAmount": line.asseseble_value,
                    "sgstRate": line.sgst_rate,
                    "cgstRate": line.cgst_rate,
                    "igstRate": line.igst_rate,
                    "cessRate": line.cess_rate})
            data.update({'itemList': lines})
        data_store['billLists'].append(data)
        self.file = base64.encodestring(json.dumps(data_store).encode('utf-8'))
        return {
            'name': _("Export Eway Bill"),
            'type': 'ir.actions.act_window',
            'view_type': 'from',
            'view_mode': 'form',
            'res_model': 'export.eway.bill',
            'res_id': self.id,
            'target': 'new',
        }
