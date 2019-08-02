# Copyright 2013-2014 Odoo SA
# Copyright 2015-2017 Chafique Delli <chafique.delli@akretion.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    'name': 'Inter Company Module for Invoices',
    'summary': 'Intercompany invoice rules',
    'version': '1.0.1.1.1',
    'category': 'Accounting & Finance',
    'website': 'https://gitlab.com/flectra-community/multi-company',
    'author': 'Odoo SA, Akretion, Odoo Community Association (OCA)',
    'license': 'AGPL-3',
    'depends': [
        'account',
        'onchange_helper',
        'base_branch_company',
    ],
    'data': [
        'views/res_config_settings_view.xml',
        'views/account_invoice_view.xml',
    ],
    'installable': True,
}
