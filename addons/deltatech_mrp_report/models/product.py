# -*- coding: utf-8 -*-
# ©  2015-2018 Deltatech
# See README.rst file on addons root folder for license details

from flectra import api, fields, models, tools, _
from flectra.exceptions import ValidationError
from flectra.osv import expression

import flectra.addons.decimal_precision as dp


class ProductCategory(models.Model):
    _inherit = "product.category"

    way_production = fields.Selection([
        ('consumption', 'Consumption in production'),
        ('receipt', 'Receipt from production'),
        ('both', 'Consumption and Receipt')], default='both', string='Production Way'
    )
