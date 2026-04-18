# -*- coding: utf-8 -*-
"""
POS Payment Method — Orbit Stripe Contactless Terminal
====================================================
Registers 'orbit_stripe_contactless_payment' as a POS payment terminal and exposes
the RPC methods that the POS JavaScript frontend calls via JSON-RPC.

Supports both TEST mode (simulated readers) and LIVE mode (real hardware /
Tap to Pay on iPhone / Tap to Pay on Android).

All contactless payment types accepted in the UK:
  - Physical cards: Visa, Mastercard, Amex, Maestro
  - Apple Pay (iOS) via Tap to Pay on iPhone or any Stripe Terminal reader
  - Google Pay (Android) via Tap to Pay on Android or any Stripe Terminal reader
  - Samsung Pay and other NFC wallets
"""
import logging

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError

_logger = logging.getLogger(__name__)


class PosPaymentMethod(models.Model):
    _inherit = 'pos.payment.method'

    # ------------------------------------------------------------------
    # Fields
    # ------------------------------------------------------------------

    orbit_stripe_reader_id = fields.Char(
        string='Stripe Reader ID (Override)',
        copy=False,
        help=(
            'Optional: assign a specific Stripe reader (tmr_...) to this payment method.\n'
            'Leave blank to use the global reader from Settings → Stripe Terminal.\n\n'
            'For Tap to Pay on iPhone/Android: the reader ID is provided automatically '
            'by the Stripe Terminal mobile SDK — leave this blank.'
        ),
    )

    # ------------------------------------------------------------------
    # Register terminal in selection dropdown
    # ------------------------------------------------------------------

    def _get_payment_terminal_selection(self):
        return super()._get_payment_terminal_selection() + [
            ('orbit_stripe_terminal', 'Stripe Terminal (Orbit)'),
        ]

    # ------------------------------------------------------------------
    # Helper: get service
    # ------------------------------------------------------------------

    def _get_stripe_service(self):
        return self.env['stripe.terminal.service']

    def _get_resolved_orbit_stripe_reader_id(self):
        """Resolve payment-method override first, then the global Stripe setting."""
        self.ensure_one()
        return (
            self.orbit_stripe_reader_id
            or self.env['ir.config_parameter'].sudo().get_param(
                'orbit_stripe_contactless_payment.reader_id', ''
            )
        )

    # ------------------------------------------------------------------
    # RPC: Runtime Config (refresh current settings inside an open POS)
    # ------------------------------------------------------------------

    @api.model
    def orbit_stripe_runtime_config(self):
        """
        Return the current Stripe Terminal settings for the POS frontend.

        The POS config is normally loaded once when the session starts, so a
        cashier can otherwise keep using stale test/live mode values after a
        manager changes Settings in the backend.
        """
        if not self.env.user.has_group('point_of_sale.group_pos_user'):
            raise AccessError(_('Access denied: POS user required.'))

        icp = self.env['ir.config_parameter'].sudo()
        test_mode_raw = icp.get_param('orbit_stripe_contactless_payment.test_mode', 'True')
        return {
            'test_mode': test_mode_raw not in ('False', '0', 'false'),
            'reader_id': icp.get_param('orbit_stripe_contactless_payment.reader_id', ''),
            'publishable_key': icp.get_param(
                'orbit_stripe_contactless_payment.publishable_key', ''
            ),
        }

    # ------------------------------------------------------------------
    # RPC: Connection Token (called by POS JS SDK initialisation)
    # ------------------------------------------------------------------

    @api.model
    def orbit_stripe_connection_token(self):
        """
        Return a Stripe Terminal connection token for JS SDK initialisation.

        Called once per POS session start. The token is single-use and
        must not be cached. The SDK calls this again when expired.

        Returns:
            {'secret': 'tok_...'} or {'error': 'message'}
        """
        if not self.env.user.has_group('point_of_sale.group_pos_user'):
            raise AccessError(_('Access denied: POS user required.'))
        try:
            return self._get_stripe_service().get_connection_token()
        except Exception as e:
            _logger.exception('orbit_stripe_connection_token error')
            return {'error': str(e)}

    # ------------------------------------------------------------------
    # RPC: Create PaymentIntent (called when cashier hits "Send")
    # ------------------------------------------------------------------

    def orbit_stripe_payment_intent(self, amount):
        """
        Create a Stripe PaymentIntent for a POS card-present payment.

        Uses capture_method='manual' so the JS SDK can call processPayment()
        before we explicitly capture. This is required by Stripe Terminal SDK.

        Args:
            amount (float): Amount in the journal's currency (e.g. 12.50 for £12.50).

        Returns:
            dict: Stripe PaymentIntent with 'client_secret', 'id', 'currency', etc.
                  or {'error': 'message'}.
        """
        self.ensure_one()
        if not self.env.user.has_group('point_of_sale.group_pos_user'):
            raise AccessError(_('Access denied: POS user required.'))

        # Resolve currency: journal currency → company currency → GBP
        currency_rec = (
            self.journal_id.currency_id
            or self.company_id.currency_id
            or self.env.company.currency_id
        )
        currency_code = (currency_rec.name or 'GBP').lower()

        # Odoo POS sends amount in DISPLAY units (e.g. 18.58 for £18.58)
        # Use the same formula as pos_stripe: round(amount / currency.rounding)
        # For GBP: rounding=0.01, so 18.58 / 0.01 = 1858 pence ✅
        currency_rounding = currency_rec.rounding if currency_rec and currency_rec.rounding else 0.01
        amount_int = int(round(amount / currency_rounding))

        _logger.info(
            'POS PaymentIntent: method=%s amount=%.2f %s rounding=%s → %s smallest units',
            self.name, amount, currency_code, currency_rounding, amount_int
        )

        try:
            svc = self._get_stripe_service()
            client = svc._get_stripe_client()
            payment_method_types = svc._get_payment_method_types(currency_code)
            params = {
                'amount': amount_int,
                'currency': currency_code,
                'payment_method_types': payment_method_types,
                'capture_method': 'manual',
                'description': 'POS — %s' % (self.env.company.name or 'Orbit'),
                'metadata': {
                    'odoo_pos_payment_method': self.name,
                    'odoo_company': self.env.company.name,
                    'odoo_user': self.env.user.name,
                },
            }
            result = svc._safe_call(client.v1.payment_intents.create, params)
            if result.get('error'):
                _logger.error('orbit_stripe_payment_intent error: %s', result['error'])
            return result
        except Exception as e:
            _logger.exception('orbit_stripe_payment_intent unexpected error')
            return {'error': str(e)}

    def orbit_stripe_process_reader_payment(self, payment_intent_id):
        """
        Instruct the configured Stripe reader to collect a card-present payment.

        This path uses Stripe's server-side reader API instead of the browser
        SDK, so it works with the configured global/override reader even when
        the POS device is not on the same local network as the reader.
        """
        self.ensure_one()
        if not self.env.user.has_group('point_of_sale.group_pos_user'):
            raise AccessError(_('Access denied: POS user required.'))

        reader_id = self._get_resolved_orbit_stripe_reader_id()
        _logger.info(
            'POS reader payment request: method=%s reader=%s intent=%s',
            self.name, reader_id or '(unset)', payment_intent_id
        )
        try:
            return self._get_stripe_service().process_reader_payment(
                payment_intent_id, reader_id=reader_id
            )
        except Exception as e:
            _logger.exception('orbit_stripe_process_reader_payment unexpected error')
            return {'error': str(e)}

    @api.model
    def orbit_stripe_retrieve_payment_intent(self, payment_intent_id):
        """Retrieve the latest PaymentIntent state for POS polling."""
        if not self.env.user.has_group('point_of_sale.group_pos_user'):
            raise AccessError(_('Access denied: POS user required.'))
        try:
            return self._get_stripe_service().retrieve_payment_intent(payment_intent_id)
        except Exception as e:
            _logger.exception('orbit_stripe_retrieve_payment_intent unexpected error')
            return {'error': str(e)}

    # ------------------------------------------------------------------
    # RPC: Capture (called after processPayment succeeds in JS)
    # ------------------------------------------------------------------

    @api.model
    def orbit_stripe_capture_payment(self, payment_intent_id, amount=None):
        """
        Capture a Stripe PaymentIntent after the card has been tapped.

        Called by POS JS after terminal.processPayment() completes successfully.

        Args:
            payment_intent_id (str): The Stripe PaymentIntent ID.
            amount (float|None):     Amount to capture (None = full amount).

        Returns:
            dict: Captured PaymentIntent or {'error': 'message'}.
        """
        if not self.env.user.has_group('point_of_sale.group_pos_user'):
            raise AccessError(_('Access denied: POS user required.'))

        svc = self._get_stripe_service()
        amount_int = None
        if amount is not None:
            currency_rec = self.env.company.currency_id
            currency_rounding = currency_rec.rounding if currency_rec and currency_rec.rounding else 0.01
            amount_int = int(round(amount / currency_rounding))

        _logger.info('Capturing POS PaymentIntent: %s (amount_int=%s)', payment_intent_id, amount_int)
        try:
            result = svc.capture_payment_intent(payment_intent_id, amount_to_capture=amount_int)
            if result.get('error'):
                _logger.error('Capture failed: %s', result['error'])
                return result

            # Newer Stripe API returns latest_charge (charge ID string), not charges dict
            # Retrieve the charge to get card brand details
            latest_charge_id = result.get('latest_charge')
            if latest_charge_id and isinstance(latest_charge_id, str):
                try:
                    client = svc._get_stripe_client()
                    charge = svc._safe_call(client.v1.charges.retrieve, latest_charge_id)
                    result['_charge'] = charge  # attach for JS to read card brand
                    _logger.info(
                        'Captured. Charge: %s | brand: %s | last4: %s | funding: %s',
                        latest_charge_id,
                        charge.get('payment_method_details', {}).get('card_present', {}).get('brand', 'unknown'),
                        charge.get('payment_method_details', {}).get('card_present', {}).get('last4', '????'),
                        charge.get('payment_method_details', {}).get('card_present', {}).get('funding', 'unknown'),
                    )
                except Exception as ce:
                    _logger.warning('Could not retrieve charge details (non-fatal): %s', ce)

            _logger.info('POS PaymentIntent %s captured successfully. Status: %s',
                         payment_intent_id, result.get('status'))
            return result
        except Exception as e:
            _logger.exception('orbit_stripe_capture_payment unexpected error')
            return {'error': str(e)}

    # ------------------------------------------------------------------
    # RPC: Cancel (called when cashier clicks Cancel)
    # ------------------------------------------------------------------

    @api.model
    def orbit_stripe_cancel_payment(self, payment_intent_id):
        """
        Cancel a Stripe PaymentIntent.

        Safe to call if payment is already cancelled or succeeded.

        Returns:
            {'success': True} or {'error': 'message'}
        """
        if not self.env.user.has_group('point_of_sale.group_pos_user'):
            raise AccessError(_('Access denied: POS user required.'))
        try:
            return self._get_stripe_service().cancel_payment_intent(payment_intent_id)
        except Exception as e:
            _logger.exception('orbit_stripe_cancel_payment unexpected error')
            return {'error': str(e)}

    # ------------------------------------------------------------------
    # RPC: Refund (called when cashier initiates POS refund)
    # ------------------------------------------------------------------

    @api.model
    def orbit_stripe_refund_payment(self, payment_intent_id, amount=None,
                                    reason='requested_by_customer'):
        """
        Issue a full or partial refund for a captured POS payment.

        Called by the POS JS when send_payment_reversal() is triggered
        (cashier presses Refund on a completed order line).

        Args:
            payment_intent_id (str): The Stripe PaymentIntent ID to refund.
            amount (float|None):     Amount to refund in journal currency (e.g. 5.00 for £5).
                                     None = full refund.
            reason (str):            'requested_by_customer', 'duplicate', or 'fraudulent'.

        Returns:
            dict: {'success': True, 'refund_id': 're_...', 'amount': float}
                  or {'error': 'message'}
        """
        if not self.env.user.has_group('point_of_sale.group_pos_user'):
            raise AccessError(_('Access denied: POS user required.'))

        _logger.info('POS refund request: pi=%s amount=%s reason=%s',
                     payment_intent_id, amount, reason)

        svc = self._get_stripe_service()
        amount_int = None
        if amount is not None:
            currency_rec = self.env.company.currency_id
            currency_rounding = currency_rec.rounding if currency_rec and currency_rec.rounding else 0.01
            amount_int = int(round(amount / currency_rounding))

        try:
            result = svc.create_refund(
                payment_intent_id=payment_intent_id,
                amount=amount_int,
                reason=reason,
                metadata={
                    'odoo_pos_refund': 'true',
                    'odoo_user': self.env.user.name,
                },
            )
            if result.get('error'):
                _logger.error('POS refund failed: %s', result['error'])
                return result

            refund_amount_float = (result.get('amount') or 0) / 100.0
            _logger.info('POS refund successful: %s £%.2f', result.get('id'), refund_amount_float)

            # Also update the backend StripeTerminalPayment record if it exists
            payment_rec = self.env['stripe.terminal.payment'].sudo().search([
                ('stripe_payment_intent_id', '=', payment_intent_id)
            ], limit=1)
            if payment_rec:
                payment_rec.action_refund_payment(
                    refund_amount=amount,
                    reason=reason,
                    note='Refund initiated from POS',
                )

            return {
                'success': True,
                'refund_id': result.get('id'),
                'amount': refund_amount_float,
                'status': result.get('status'),
            }
        except Exception as e:
            _logger.exception('orbit_stripe_refund_payment unexpected error')
            return {'error': str(e)}
