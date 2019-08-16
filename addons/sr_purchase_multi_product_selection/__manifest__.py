# -*- coding: utf-8 -*-
##############################################################################
#
#    This module uses Flectra, Open Source Management Solution Framework.
#    Copyright (C) 2017-Today Sitaram
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>
#
##############################################################################

{
    'name': "Purchase Order Multi Product Selection",
    'version': "11.0.0.2",
    'summary': "This module allows you to select Multiple product in purchase order at a time on single click.",
    'category': 'Purchases',
    'description': """
        This module allows you to select Multiple product in purchase order on single click.
         Purchase order add multi product
         product add
         multiple product add in purchase order quickly
         easy add product in purchase order on single click
         create purchase order from product
    """,
    'author': "Sitaram",
    'website': " ",
    'depends': ['base', 'purchase', 'product'],
    'data': [
                'security/ir.model.access.csv',
        'views/purchase.xml',
        'views/product.xml'
    ],
    'demo': [],
    "license": "AGPL-3",
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': True,
    'auto_install': False,
}
