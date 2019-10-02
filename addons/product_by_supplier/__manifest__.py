# Copyright 2010-2013 Elico Corp. <lin.yu@elico-corp.com>
# Copyright 2017 Eficent Business and IT Consulting Services S.L.
#   (http://www.eficent.com)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

{
    'name': 'Product by Supplier info',
    'version': '1.0.1.0.0',
    'development_status': 'Mature',
    'category': 'Purchase Management',
    'summary': 'Show products grouped by suppliers',
    'author': "Elico Corp,, Flectra Community"
              "Odoo Community Association (OCA)",
    'website': 'https://gitlab.com/flectra-community/purchase-workflow',
    'license': 'AGPL-3',
    'depends': [
        'product',
        'purchase',
    ],
    'data': [
        'views/product_supplierinfo_view.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
