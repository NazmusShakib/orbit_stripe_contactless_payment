# -*- coding: utf-8 -*-
"""
res_config_settings.py
========================
Extends Odoo's Settings (res.config.settings) to add Stripe Terminal
configuration fields. All values are stored as ir.config_parameter
system parameters so they are never hardcoded and can be changed at runtime.

Fields added to Settings > Technical > Stripe Terminal:
  - Stripe Secret Key        (test key, sk_test_...)
  - Stripe Publishable Key   (test key, pk_test_...)
  - Stripe Terminal Location ID
  - Stripe Reader ID         (simulated reader for Phase 1)
  - Test Mode toggle         (always True in Phase 1)
"""

import logging
from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)

# Prefix used for all ir.config_parameter keys in this module
_PARAM_PREFIX = 'orbit_stripe_contactless_payment'


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # ── Stripe API Keys ───────────────────────────────────────────────────────
    stripe_secret_key = fields.Char(
        string='Stripe Secret Key',
        help='Stripe secret key for test mode (starts with sk_test_). '
             'Never use a live key in Phase 1.',
        config_parameter=f'{_PARAM_PREFIX}.secret_key',
    )
    stripe_publishable_key = fields.Char(
        string='Stripe Publishable Key',
        help='Stripe publishable key for test mode (starts with pk_test_).',
        config_parameter=f'{_PARAM_PREFIX}.publishable_key',
    )

    # ── Terminal Configuration ────────────────────────────────────────────────
    stripe_terminal_location_id = fields.Char(
        string='Stripe Terminal Location ID',
        help='The Stripe Terminal Location ID (e.g. tml_xxxx). '
             'Create one in the Stripe Dashboard under Terminal > Locations.',
        config_parameter=f'{_PARAM_PREFIX}.location_id',
    )
    stripe_reader_id = fields.Char(
        string='Stripe Reader ID',
        help='The Stripe Terminal Reader ID (e.g. tmr_xxxx). '
             'For Phase 1 simulation, use the simulated reader ID from Stripe Dashboard.',
        config_parameter=f'{_PARAM_PREFIX}.reader_id',
    )

    # ── Mode ──────────────────────────────────────────────────────────────────
    stripe_test_mode = fields.Boolean(
        string='Test Mode',
        help='Enable Stripe test/sandbox mode. '
             'MUST be True in Phase 1 (dev). Disable only when real hardware is ready.',
    )

    # ── Webhook (Phase 2 placeholder) ─────────────────────────────────────────
    stripe_tip_enabled = fields.Boolean(
        string='Enable Tip / Gratuity',
        config_parameter='orbit_stripe_contactless_payment.tip_enabled',
        help='Show a tip selection popup before the customer taps their card in POS.',
    )
    stripe_tip_percentages = fields.Char(
        string='Tip Percentages',
        config_parameter='orbit_stripe_contactless_payment.tip_percentages',
        default='10,15,20',
        help='Comma-separated tip percentage options (e.g. 10,15,20).',
    )
    stripe_webhook_secret = fields.Char(
        string='Stripe Webhook Secret',
        help='[Phase 2] Webhook signing secret for verifying Stripe events (whsec_xxxx). '
             'Leave blank in Phase 1.',
        config_parameter=f'{_PARAM_PREFIX}.webhook_secret',
    )

    @api.model
    def get_values(self):
        """Parse the test-mode parameter explicitly so False stays False."""
        res = super().get_values()
        test_mode_raw = self.env['ir.config_parameter'].sudo().get_param(
            f'{_PARAM_PREFIX}.test_mode', 'True'
        )
        res['stripe_test_mode'] = test_mode_raw not in ('False', '0', 'false', '')
        return res

    def set_values(self):
        """
        Persist test mode explicitly.

        Odoo's generic config_parameter handling for booleans stores False by
        removing the parameter, which clashes with this field's default=True
        and makes the settings screen show the toggle as enabled again.
        """
        super().set_values()
        self.ensure_one()
        self.env['ir.config_parameter'].sudo().set_param(
            f'{_PARAM_PREFIX}.test_mode',
            'True' if self.stripe_test_mode else 'False',
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Validation
    # ─────────────────────────────────────────────────────────────────────────

    @api.constrains('stripe_secret_key')
    def _check_secret_key(self):
        for rec in self:
            if rec.stripe_secret_key and not rec.stripe_secret_key.startswith('sk_'):
                raise models.ValidationError(
                    _('Stripe Secret Key must start with "sk_". '
                      'Use "sk_test_..." for test mode.')
                )

    @api.constrains('stripe_publishable_key')
    def _check_publishable_key(self):
        for rec in self:
            if rec.stripe_publishable_key and not rec.stripe_publishable_key.startswith('pk_'):
                raise models.ValidationError(
                    _('Stripe Publishable Key must start with "pk_". '
                      'Use "pk_test_..." for test mode.')
                )

    # ─────────────────────────────────────────────────────────────────────────
    # Helper: read current config (used by services)
    # ─────────────────────────────────────────────────────────────────────────

    def _sync_stripe_config_parameters(self):
        """Persist the current form values so follow-up actions see fresh settings."""
        self.ensure_one()
        icp = self.env['ir.config_parameter'].sudo()
        icp.set_param(f'{_PARAM_PREFIX}.secret_key', self.stripe_secret_key or '')
        icp.set_param(
            f'{_PARAM_PREFIX}.publishable_key', self.stripe_publishable_key or ''
        )
        icp.set_param(
            f'{_PARAM_PREFIX}.location_id', self.stripe_terminal_location_id or ''
        )
        icp.set_param(f'{_PARAM_PREFIX}.reader_id', self.stripe_reader_id or '')
        icp.set_param(
            f'{_PARAM_PREFIX}.test_mode', 'True' if self.stripe_test_mode else 'False'
        )
        icp.set_param(
            f'{_PARAM_PREFIX}.tip_enabled', 'True' if self.stripe_tip_enabled else 'False'
        )
        icp.set_param(
            f'{_PARAM_PREFIX}.tip_percentages', self.stripe_tip_percentages or '10,15,20'
        )
        icp.set_param(f'{_PARAM_PREFIX}.webhook_secret', self.stripe_webhook_secret or '')

    def action_open_setup_wizard(self):
        """Open the Stripe Terminal Setup & Test wizard from Settings."""
        self.ensure_one()
        self._sync_stripe_config_parameters()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Stripe Terminal Setup & Test',
            'res_model': 'stripe.setup.wizard',
            'view_mode': 'form',
            'target': 'new',
        }

    @api.model
    def get_stripe_config(self):
        """
        Returns a dict with all Stripe configuration values from ir.config_parameter.
        Use this helper from services/controllers instead of reading params directly.
        """
        get = lambda key: self.env['ir.config_parameter'].sudo().get_param(
            f'{_PARAM_PREFIX}.{key}', ''
        )
        return {
            'secret_key': get('secret_key'),
            'publishable_key': get('publishable_key'),
            'location_id': get('location_id'),
            'reader_id': get('reader_id'),
            'test_mode': self.env['ir.config_parameter'].sudo().get_param(
                f'{_PARAM_PREFIX}.test_mode', 'True'
            ) not in ('False', '0', 'false', ''),
            'webhook_secret': get('webhook_secret'),
        }
