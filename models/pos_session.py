# -*- coding: utf-8 -*-
"""
POS Session — inject Stripe Terminal config into POS frontend
"""
from odoo import models


class PosSession(models.Model):
    _inherit = 'pos.session'

    def _loader_params_pos_payment_method(self):
        """Include orbit_stripe_reader_id when loading payment methods into POS."""
        result = super()._loader_params_pos_payment_method()
        result['search_params']['fields'].append('orbit_stripe_reader_id')
        return result

    def _get_pos_ui_pos_config(self, params):
        """
        Inject Stripe Terminal configuration into the POS UI config dict.

        The POS JS frontend reads these values as:
            this.pos.config.orbit_stripe_test_mode
            this.pos.config.orbit_stripe_reader_id
            this.pos.config.orbit_stripe_publishable_key
        """
        result = super()._get_pos_ui_pos_config(params)
        ICP = self.env['ir.config_parameter'].sudo()

        test_mode_raw = ICP.get_param('orbit_stripe_contactless_payment.test_mode', 'True')
        result['orbit_stripe_test_mode'] = test_mode_raw not in ('False', '0', 'false')
        result['orbit_stripe_reader_id'] = ICP.get_param(
            'orbit_stripe_contactless_payment.reader_id', '')
        result['orbit_stripe_publishable_key'] = ICP.get_param(
            'orbit_stripe_contactless_payment.publishable_key', '')
        # Tip / gratuity config
        result['orbit_stripe_tip_enabled'] = ICP.get_param(
            'orbit_stripe_contactless_payment.tip_enabled', 'False'
        ) in ('True', '1', 'true')
        result['orbit_stripe_tip_percentages'] = ICP.get_param(
            'orbit_stripe_contactless_payment.tip_percentages', '10,15,20')
        return result
