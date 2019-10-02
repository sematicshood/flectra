# Copyright 2016 Eficent Business and IT Consulting Services S.L.
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

{
    "name": "Purchase Minimum Amount",
    "author": "Eficent, Odoo Community Association (OCA)",
    "version": "1.0.1.0.0",
    "website": "https://gitlab.com/flectra-community/purchase-workflow",
    "depends": [
        'purchase',
        'purchase_order_approval_block',
    ],
    "data": [
        'data/purchase_block_reason_data.xml',
        'views/purchase_order_view.xml',
        'views/res_partner_view.xml',
    ],
    "license": 'LGPL-3',
    "installable": True
}
