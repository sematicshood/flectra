# Copyright 2017 Eficent Business and IT Consulting Services, S.L.
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).

from flectra import models


class ProcurementRule(models.Model):
    _inherit = 'procurement.rule'

    def _get_stock_move_values(self, product_id, product_qty, product_uom,
                               location_id, name, origin, values, group_id):
        result = super(ProcurementRule, self)._get_stock_move_values(
            product_id, product_qty, product_uom, location_id, name, origin,
            values, group_id)
        if values.get('stock_request_id', False):
            result['allocation_ids'] = [(0, 0, {
                'stock_request_id': values['stock_request_id'],
                'requested_product_uom_qty': product_qty,
            })]
        return result
