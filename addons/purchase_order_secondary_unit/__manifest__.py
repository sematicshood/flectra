# Copyright 2018 Tecnativa - Sergio Teruel
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    'name': 'Purchase Order Secondary Unit',
    'summary': 'Purchase product in a secondary unit',
    'version': '1.0.1.0.0',
    'development_status': 'Beta',
    'category': 'Purchase',
    'website': 'https://gitlab.com/flectra-community/purchase-workflow',
    'author': 'Tecnativa, Odoo Community Association (OCA)',
    'license': 'AGPL-3',
    'application': False,
    'installable': True,
    'auto_install': True,
    'depends': [
        'purchase',
        'product_secondary_unit',
    ],
    'data': [
        'views/product_views.xml',
        'views/purchase_order_views.xml',
    ],
}
