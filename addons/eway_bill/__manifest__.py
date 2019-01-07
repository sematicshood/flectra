# Part of Flectra See LICENSE file for full copyright and licensing details.

{
    'name': 'E-way Bill',
    'version': '1.0',
    'author': 'FlectraHQ',
    'website': 'https://flectrahq.com',
    'category': 'Accounting',
    'summary': 'Electronic-way bill',
    'depends': ['account_invoicing', 'l10n_in', 'stock'],
    'data': [
        'security/ir.model.access.csv',
        'data/product_uom_data.xml',
        'data/sub_type_data.xml',
        'data/eway_bill_sequence.xml',
        'wizard/create_eway_bill_view.xml',
        'wizard/export_eway_bill_view.xml',
        'views/product_uom_view.xml',
        'views/res_partner_view.xml',
        'views/res_company_view.xml',
        'views/account_invoice_view.xml',
        'views/res_config_settings_views.xml',
        'views/eway_bill_view.xml',
        'views/stock_picking_view.xml',
        'views/menuitems_view.xml',
        
    ],
    'demo': [
        'demo/res_partner_demo.xml',
        'demo/account_account_demo.xml',
        'demo/account_invoice_demo.xml',
        'demo/eway_bill_demo.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': True,
}
