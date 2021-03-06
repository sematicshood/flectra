# Copyright (C) 2018 Eficent Business and IT Consulting Services S.L.
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from flectra import fields, models


class PurchaseConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    group_purchase_blanket_disable_adding_lines = fields.Boolean(
        string='Disable adding more lines to SOs',
        implied_group='purchase_blanket_order.'
                      'purchase_blanket_orders_disable_adding_lines')
