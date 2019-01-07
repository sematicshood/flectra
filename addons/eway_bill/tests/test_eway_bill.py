# Part of Flectra See LICENSE file for full copyright and licensing details.

import logging
from flectra.tests.common import TransactionCase


class TestCreateEway(TransactionCase):
    def setUp(self):
        super(TestCreateEway, self).setUp()

    def test_invoice(self):
        # Add tax for product

        product = self.env.ref('product.product_product_5')
        self.eway_wizard = self.env['generate.eway.bill']
        self.eway_bill = self.env['eway.bill']

        self.res_user_model = self.env['res.users']
        self.sub_type = self.env['sub.type'].search([('code', '=', 1)])
        self.main_company = self.env.ref('base.main_company')
        self.main_partner = self.env.ref('base.main_partner')
        self.main_bank = self.env.ref('base.res_bank_1')
        res_users_account_user = self.env.ref('account.group_account_invoice')
        fiscal_position_id = self.env.ref('l10n_in.fiscal_position_in_inter_state')
        res_users_account_manager = self.env.ref('account.group_account_manager')
        partner_manager = self.env.ref('base.group_partner_manager')
        self.tax_model = self.env['account.tax']
        self.account_model = self.env['account.account']
        self.account_type_model = self.env['account.account.type']
        self.currency_euro = self.env.ref('base.EUR')
        self.account_manager = self.res_user_model.with_context({'no_reset_password': True}).create(dict(
            name="Adviser",
            company_id=self.main_company.id,
            login="fm",
            email="accountmanager@yourcompany.com",
            groups_id=[(6, 0, [res_users_account_manager.id, partner_manager.id])]
        ))
        self.ova = self.env['account.account'].search([('user_type_id', '=', self.env.ref('account.data_account_type_current_assets').id)], limit=1)

        invoice_line_data = [(0, 0, {'name': product.name, 
            'product_id': product.id, 
            'quantity': 10.0, 
            'uom_id': product.uom_id.id, 
            'price_unit': product.standard_price, 
            'account_id': self.env['account.account'].search([('user_type_id', '=', self.env.ref('account.data_account_type_revenue').id)], limit=1).id})]


        self.account_model = self.env['account.account']
        self.account_invoice_obj = self.env['account.invoice']
        self.payment_term = self.env.ref('account.account_payment_term_advance')
        self.journalrec = self.env['account.journal'].search([('type', '=', 'sale')])[0]
        self.partner3 = self.env.ref('base.res_partner_3')
        account_user_type = self.env.ref('account.data_account_type_receivable')
        self.account_recc_id = self.account_model.sudo(self.account_manager.id).create(dict(
            code="cust_acc",
            name="customer account",
            user_type_id=account_user_type.id,
            reconcile=True,
        ))

        self.account_invoice_customer = self.account_invoice_obj.create(dict(
            name="Test Customer Invoice",
            reference_type="none",
            payment_term_id=self.payment_term.id,
            journal_id=self.journalrec.id,
            partner_id=self.partner3.id,
            account_id=self.account_recc_id.id,
            invoice_line_ids=invoice_line_data,
        ))


        # # I manually assign tax on invoice
        # invoice_tax_line = {
        #     'name': 'Test Tax for Customer Invoice',
        #     'manual': 1,
        #     'amount': 9050,
        #     'account_id': self.ova.id,
        #     'invoice_id': self.account_invoice_customer.id,
        # }
        # tax = self.env['account.invoice.tax'].create(invoice_tax_line)

        # total_before_confirm = self.partner3.total_invoiced

        # I check that Initially customer invoice is in the "Draft" state
        self.assertEquals(self.account_invoice_customer.state, 'draft')

        # I check that there is no move attached to the invoice
        self.assertEquals(len(self.account_invoice_customer.move_id), 0)

        # I validate invoice by creating on
        self.account_invoice_customer.action_invoice_open()

        # I check that the invoice state is "Open"
        self.assertEquals(self.account_invoice_customer.state, 'open')

        self.account_invoice_customer.create_picking()
        
        self.assertTrue(self.account_invoice_customer.picking_ids, 'Stock: no picking created for "invoice on delivery" stockable products')

        pick = self.account_invoice_customer.picking_ids
        pick.force_assign()
        pick.move_lines.write({'quantity_done': 10})
        self.assertTrue(pick.button_validate(), 'Stock: complete delivery should not need a backorder')
        del_qties = [inv.qty_delivered for inv in self.account_invoice_customer.invoice_line_ids]
        del_qties_truth = [10.0 if inv.product_id.type in ['product', 'consu'] else 0.0 for inv in self.account_invoice_customer.invoice_line_ids]
        self.assertEqual(del_qties, del_qties_truth, 'Stock: delivered quantities are wrong after partial deliver quantities are wrong after partial delivery')

        context_dict = {'active_model': 'account.invoice','active_ids':[self.account_invoice_customer.id]}
        eway_vals = self.eway_wizard.with_context(context_dict).default_get([])
        eway_vals.update({
            'sub_type_id': self.sub_type.id,
        })
        
        self.eway = self.eway_wizard.with_context(context_dict).create(eway_vals)
        self.eway.generate_eway()
        self.assertTrue(self.eway.id, 'Eway Bill: no eway bill created for invoice')

        self.eway_bill = self.account_invoice_customer.eway_bill_id

        self.assertEquals(self.eway_bill.state, 'draft')
        self.eway_bill.action_confirm()
        self.assertEquals(self.eway_bill.state, 'confirm')
