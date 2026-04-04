# -*- coding: utf-8 -*-
"""
stripe_setup_wizard.py
=======================
Transient wizard for Stripe Terminal setup actions available directly in Odoo:
  1. Test Stripe API connection
  2. Create a simulated reader (Phase 1)
  3. Auto-save the reader ID to Settings

Accessible from Settings → Stripe Terminal → "Setup & Test" button.
"""
import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class StripeSetupWizard(models.TransientModel):
    _name = 'stripe.setup.wizard'
    _description = 'Stripe Terminal Setup Wizard'

    # ── State / Results ───────────────────────────────────────────────────────
    state = fields.Selection([
        ('start', 'Start'),
        ('connected', 'Connected'),
        ('reader_created', 'Reader Created'),
        ('error', 'Error'),
    ], default='start', readonly=True)

    connection_message = fields.Text(string='Connection Test Result', readonly=True)
    reader_result = fields.Text(string='Reader Creation Result', readonly=True)
    reader_id_created = fields.Char(string='New Reader ID', readonly=True)

    # ── Config (read from ir.config_parameter) ───────────────────────────────
    secret_key_preview = fields.Char(
        string='Secret Key (configured)',
        compute='_compute_config_preview',
    )
    location_id_configured = fields.Char(
        string='Location ID (configured)',
        compute='_compute_config_preview',
    )
    reader_id_configured = fields.Char(
        string='Reader ID (configured)',
        compute='_compute_config_preview',
    )
    reader_label = fields.Char(
        string='New Reader Label',
        default='Odoo Dev Simulated Reader',
        help='A name to identify this simulated reader in the Stripe Dashboard.',
    )

    @api.depends()
    def _compute_config_preview(self):
        get = lambda k: self.env['ir.config_parameter'].sudo().get_param(
            f'orbit_stripe_contactless_payment.{k}', ''
        )
        for rec in self:
            sk = get('secret_key')
            rec.secret_key_preview = f'...{sk[-8:]}' if sk else '(not set)'
            rec.location_id_configured = get('location_id') or '(not set)'
            rec.reader_id_configured = get('reader_id') or '(not set)'

    # ─────────────────────────────────────────────────────────────────────────
    # Actions
    # ─────────────────────────────────────────────────────────────────────────

    def action_test_connection(self):
        """Test the Stripe API connection using the configured secret key."""
        self.ensure_one()
        service = self.env['stripe.terminal.service']
        try:
            client = service._get_stripe_client()
            import stripe as _stripe

            # Use connection token creation as a lightweight API test
            # (cheaper than listing payment intents and works with Terminal keys)
            result = service._safe_call(
                client.v1.terminal.connection_tokens.create, {}
            )

            if result.get('error'):
                self.write({
                    'state': 'error',
                    'connection_message': '❌ Connection FAILED:\n%s' % result['error'],
                })
            else:
                version = getattr(getattr(_stripe, 'VERSION', None) or
                                  getattr(_stripe, '_version', None), 'VERSION', 'unknown')
                mode = '🧪 TEST MODE' if service._is_test_mode() else '🔴 LIVE MODE'
                self.write({
                    'state': 'connected',
                    'connection_message': (
                        '✅ Connection SUCCESSFUL!\n'
                        'Stripe API is responding.\n'
                        'Mode: %s\n'
                        'Your API key is valid.\n'
                        'Connection token received: %s...'
                    ) % (mode, (result.get('secret') or '')[:20]),
                })
        except UserError as e:
            self.write({
                'state': 'error',
                'connection_message': '❌ Configuration Error:\n%s' % str(e),
            })
        return self._reopen()

    def action_create_simulated_reader(self):
        """Create a simulated Stripe Terminal reader and save its ID to Settings."""
        self.ensure_one()
        location_id = self.env['ir.config_parameter'].sudo().get_param(
            'orbit_stripe_contactless_payment.location_id', ''
        )
        if not location_id:
            raise UserError(
                _('Please configure the Stripe Terminal Location ID in Settings first.\n'
                  'Get it from: Stripe Dashboard → Terminal → Locations → copy tml_... ID')
            )

        service = self.env['stripe.terminal.service']
        result = service.create_simulated_reader(
            location_id=location_id,
            label=self.reader_label or 'Odoo Dev Simulated Reader',
        )

        if result.get('error'):
            self.write({
                'state': 'error',
                'reader_result': f'❌ Failed to create reader:\n{result["error"]}',
            })
        else:
            reader_id = result.get('id', '')
            # Auto-save the reader ID to ir.config_parameter
            self.env['ir.config_parameter'].sudo().set_param(
                'orbit_stripe_contactless_payment.reader_id', reader_id
            )
            self.write({
                'state': 'reader_created',
                'reader_id_created': reader_id,
                'reader_result': (
                    f'✅ Simulated reader created!\n'
                    f'Reader ID: {reader_id}\n'
                    f'Label: {result.get("label", "")}\n'
                    f'Device Type: {result.get("device_type", "simulated")}\n\n'
                    f'This ID has been automatically saved to Settings.'
                ),
            })
        return self._reopen()

    def action_list_readers(self):
        """List all readers for the configured location."""
        self.ensure_one()
        location_id = self.env['ir.config_parameter'].sudo().get_param(
            'orbit_stripe_contactless_payment.location_id', ''
        )
        service = self.env['stripe.terminal.service']
        result = service.list_readers(location_id=location_id or None)

        if result.get('error'):
            self.write({
                'state': 'error',
                'reader_result': f'❌ Failed to list readers:\n{result["error"]}',
            })
        else:
            readers = result.get('readers', [])
            if readers:
                lines = [f'Found {len(readers)} reader(s):\n']
                for r in readers:
                    lines.append(
                        f'  • {r["id"]} | {r["label"] or "(no label)"} | '
                        f'{r["device_type"]} | status: {r["status"]}'
                    )
                msg = '\n'.join(lines)
            else:
                msg = 'No readers found for the configured location.'
            self.write({'reader_result': msg})
        return self._reopen()

    def action_save_reader_id(self):
        """Save the newly created reader ID to Settings (if not already auto-saved)."""
        self.ensure_one()
        if self.reader_id_created:
            self.env['ir.config_parameter'].sudo().set_param(
                'orbit_stripe_contactless_payment.reader_id', self.reader_id_created
            )
        return self._reopen()

    def _reopen(self):
        """Return action to reopen this wizard (stay in the dialog)."""
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'stripe.setup.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
