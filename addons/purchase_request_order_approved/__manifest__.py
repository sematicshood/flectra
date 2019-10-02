# Copyright 2017 Eficent Business and IT Consulting Services S.L.
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl-3.0).

{
    "name": "Purchase Request Order Approved",
    "author": "Eficent, "
              "Odoo Community Association (OCA)",
    "version": "1.0.1.0.0",
    "website": "https://gitlab.com/flectra-community/purchase-workflow",
    "category": "Purchase Management",
    "depends": [
        "purchase_request",
        "purchase_order_approved",
    ],
    "data": [
        "views/purchase_request_view.xml",
    ],
    "license": 'LGPL-3',
    "installable": True,
    "post_init_hook": 'post_init_hook',
    "auto_install": True,
}
