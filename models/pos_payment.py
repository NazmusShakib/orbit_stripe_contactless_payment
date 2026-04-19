# -*- coding: utf-8 -*-
"""
POS Payment linkage for Orbit Stripe Terminal.

Links synced POS payments back to the corresponding stripe.terminal.payment
audit record so backend refund actions can use the real Odoo POS refund flow.
"""

from odoo import api, models


class PosPayment(models.Model):
    _inherit = 'pos.payment'

    def _sync_orbit_stripe_payment_records(self):
        terminal_payment_model = self.env['stripe.terminal.payment']
        for payment in self.filtered(
            lambda rec: rec.payment_method_id.use_payment_terminal == 'orbit_stripe_terminal'
        ):
            terminal_payment_model.link_from_pos_payment(payment)

    @api.model_create_multi
    def create(self, vals_list):
        payments = super().create(vals_list)
        payments._sync_orbit_stripe_payment_records()
        return payments

    def write(self, vals):
        result = super().write(vals)
        if any(field in vals for field in ('transaction_id', 'payment_method_id', 'pos_order_id')):
            self._sync_orbit_stripe_payment_records()
        return result
