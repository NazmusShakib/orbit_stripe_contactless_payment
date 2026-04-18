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
        config = self.env['stripe.terminal.service']._get_terminal_config()

        result['orbit_stripe_test_mode'] = config['test_mode']
        result['orbit_stripe_reader_id'] = config['reader_id']
        result['orbit_stripe_publishable_key'] = config['publishable_key']
        result['orbit_stripe_tip_enabled'] = config['tip_enabled']
        result['orbit_stripe_tip_percentages'] = config['tip_percentages']
        return result
