# Copyright 2017 Eficent Business and IT Consulting Services, S.L.
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).

from flectra import models


class ProcurementRule(models.Model):
    _inherit = 'procurement.rule'

    def _get_stock_move_values(self, product_id, product_qty, product_uom,
                               location_id, name, origin, values, group_id):
        vals = super(ProcurementRule, self)._get_stock_move_values(
            product_id, product_qty, product_uom,
            location_id, name, origin, values, group_id)
        if 'orderpoint_id' in values:
            vals['orderpoint_ids'] = [(4, values['orderpoint_id'].id)]
        elif 'orderpoint_ids' in values:
            vals['orderpoint_ids'] = [(4, o.id)
                                      for o in values['orderpoint_ids']]
        return vals
