# -*- coding: utf-8 -*-
"""
Stripe Terminal Service
========================
Central service model for all Stripe API calls.

Supports:
  - Test / Simulation mode  (sk_test_... keys, simulated readers)
  - Live / Production mode  (sk_live_... keys, real hardware)

UK-specific:
  - currency must be 'gbp' for GB Stripe accounts
  - payment_method_types=['card_present'] covers ALL contactless payments:
      • Physical cards (Visa, Mastercard, Amex, Maestro)
      • Apple Pay on iPhone  (Tap to Pay on iPhone)
      • Google Pay on Android (Tap to Pay on Android)
      • Samsung Pay and other NFC wallets
"""
import logging
from odoo import api, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class StripeTerminalService(models.AbstractModel):
    _name = 'stripe.terminal.service'
    _description = 'Stripe Terminal Service'

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_param(self, key, default=''):
        return self.env['ir.config_parameter'].sudo().get_param(
            f'orbit_stripe_contactless_payment.{key}', default
        )

    def _is_test_mode(self):
        return self._get_param('test_mode', 'True') not in ('False', '0', 'false')

    def _get_stripe_client(self):
        """
        Initialise and return the Stripe Python client.

        Validates that the key type (test/live) matches the configured mode.
        Raises UserError with a clear message if anything is misconfigured.
        """
        try:
            import stripe as _stripe
        except ImportError:
            raise UserError(_(
                'The "stripe" Python package is not installed.\n'
                'Run: pip install stripe\n'
                'Or add it to your requirements.txt and rebuild.'
            ))

        secret_key = self._get_param('secret_key', '')
        if not secret_key:
            raise UserError(_(
                'Stripe Secret Key is not configured.\n'
                'Go to Settings → Stripe Terminal and enter your API key.'
            ))

        is_test = self._is_test_mode()

        if is_test and secret_key.startswith('sk_live_'):
            raise UserError(_(
                'Test Mode is ON but you entered a Live key (sk_live_...).\n'
                'Either:\n'
                '  • Switch to your test key (sk_test_...), or\n'
                '  • Disable Test Mode in Settings → Stripe Terminal.'
            ))

        if not is_test and secret_key.startswith('sk_test_'):
            raise UserError(_(
                'Test Mode is OFF (Live Mode) but you entered a Test key (sk_test_...).\n'
                'Either:\n'
                '  • Enter your live key (sk_live_...), or\n'
                '  • Enable Test Mode in Settings → Stripe Terminal.'
            ))

        client = _stripe.StripeClient(secret_key)
        return client

    @api.model
    def _safe_call(self, func, *args, **kwargs):
        """
        Wrap any Stripe API call and convert Stripe exceptions to dicts.

        Returns:
            dict: the response on success, or {'error': 'message'} on failure.
        """
        try:
            result = func(*args, **kwargs)
            return self._to_dict(result)
        except Exception as e:
            try:
                import stripe as _stripe
                if isinstance(e, _stripe.StripeError):
                    msg = e.user_message or str(e)
                    _logger.error('Stripe API error [%s]: %s', type(e).__name__, msg)
                    return {'error': msg}
            except ImportError:
                pass
            _logger.exception('Unexpected error calling Stripe API')
            return {'error': str(e)}

    @api.model
    def _to_dict(self, obj):
        """
        Recursively convert any Stripe SDK object to a plain Python dict.

        Stripe SDK v2+ objects have a `to_dict()` method that returns a
        nested plain dict — we use that first, then fall back to `_data`,
        then to generic dict/list handling.
        """
        if obj is None:
            return None

        # Try to_dict() first (Stripe SDK v2+ — most reliable)
        if hasattr(obj, 'to_dict') and callable(obj.to_dict):
            try:
                raw = obj.to_dict()
                # to_dict() may still return nested StripeObjects — recurse
                return self._to_dict(raw)
            except Exception:
                pass

        # Try _data dict (internal Stripe SDK storage)
        if hasattr(obj, '_data') and isinstance(obj._data, dict):
            return {k: self._to_dict(v) for k, v in obj._data.items()}

        # Plain dict
        if isinstance(obj, dict):
            return {k: self._to_dict(v) for k, v in obj.items()}

        # List
        if isinstance(obj, list):
            return [self._to_dict(i) for i in obj]

        # Scalar (str, int, float, bool, None)
        return obj

    @api.model
    def _get_payment_method_types(self, currency):
        """
        Return the correct payment_method_types list for Stripe Terminal.

        - GBP / EUR / AUD / SGD / most currencies → ['card_present']
          Covers Visa, Mastercard, Amex, Maestro, Apple Pay, Google Pay, Samsung Pay
        - CAD → ['card_present', 'interac_present']  (Canadian Interac debit)

        'card_present' with a Stripe Terminal reader or Tap to Pay accepts ALL
        NFC/contactless payments regardless of whether the customer uses a
        physical card, Apple Pay, Google Pay, Samsung Pay or any other NFC wallet.
        """
        if (currency or '').lower() == 'cad':
            return ['card_present', 'interac_present']
        return ['card_present']

    @api.model
    def _amount_to_stripe_int(self, amount_float, currency_code):
        """
        Convert a float amount to the smallest currency unit (e.g. pence for GBP).

        Most currencies use 2 decimal places (multiply by 100).
        Zero-decimal currencies (JPY, KRW, etc.) use the integer directly.
        """
        zero_decimal = {'bif', 'clp', 'gnf', 'jpy', 'kmf', 'krw', 'mga',
                        'pyg', 'rwf', 'ugx', 'vnd', 'vuv', 'xaf', 'xof', 'xpf'}
        if (currency_code or '').lower() in zero_decimal:
            return int(round(amount_float))
        return int(round(amount_float * 100))

    # ------------------------------------------------------------------
    # Connection Token (for Stripe Terminal JS SDK)
    # ------------------------------------------------------------------

    @api.model
    def get_connection_token(self):
        """
        Create and return a Stripe Terminal connection token.

        Required by the Stripe Terminal JS SDK for reader discovery and connection.
        Tokens are single-use and must not be cached.

        Returns:
            {'secret': 'token...'} or {'error': 'message'}
        """
        client = self._get_stripe_client()
        _logger.info('Generating Stripe Terminal connection token (test=%s)', self._is_test_mode())
        return self._safe_call(client.v1.terminal.connection_tokens.create, {})

    # ------------------------------------------------------------------
    # PaymentIntent
    # ------------------------------------------------------------------

    @api.model
    def create_payment_intent(self, amount, currency='gbp', description='',
                              metadata=None, capture_method='manual'):
        """
        Create a Stripe PaymentIntent for a card-present (Terminal) payment.

        Args:
            amount (int):           Amount in smallest currency unit (pence for GBP).
            currency (str):         ISO currency code, lowercase. MUST be 'gbp' for UK.
            description (str):      Human-readable description.
            metadata (dict):        Key-value pairs attached to the PaymentIntent.
            capture_method (str):   'manual' for POS/JS SDK flow (default).
                                    'automatic' for backend-only flow.

        Returns:
            dict: Stripe PaymentIntent or {'error': 'message'}.

        UK Note:
            Stripe Terminal on GB accounts requires currency='gbp'.
            The error "card_present with currency usd is not supported in GB"
            means the currency was wrong — this method defaults to 'gbp'.
        """
        client = self._get_stripe_client()
        currency = (currency or 'gbp').lower()
        metadata = metadata or {}
        payment_method_types = self._get_payment_method_types(currency)

        params = {
            'amount': int(amount),
            'currency': currency,
            'payment_method_types': payment_method_types,
            'capture_method': capture_method,
            'description': description or 'Orbit Stripe Terminal Payment',
            'metadata': metadata,
        }

        _logger.info(
            'Creating PaymentIntent: amount=%s %s, types=%s, capture=%s',
            amount, currency, payment_method_types, capture_method
        )
        result = self._safe_call(client.v1.payment_intents.create, params)
        if not result.get('error'):
            _logger.info('PaymentIntent created: %s (status=%s)',
                         result.get('id'), result.get('status'))
        return result

    @api.model
    def retrieve_payment_intent(self, payment_intent_id):
        """Retrieve a PaymentIntent by ID."""
        client = self._get_stripe_client()
        return self._safe_call(client.v1.payment_intents.retrieve, payment_intent_id)

    @api.model
    def confirm_payment_intent(self, payment_intent_id):
        """Confirm a PaymentIntent (for backend-only flows)."""
        client = self._get_stripe_client()
        _logger.info('Confirming PaymentIntent: %s', payment_intent_id)
        return self._safe_call(client.v1.payment_intents.confirm, payment_intent_id, {})

    @api.model
    def capture_payment_intent(self, payment_intent_id, amount_to_capture=None):
        """
        Capture an authorised PaymentIntent.

        Called after the Stripe Terminal JS SDK has successfully processed the
        card tap (processPayment completed). Captures the funds.

        Args:
            payment_intent_id (str): The PaymentIntent to capture.
            amount_to_capture (int): Optional partial capture amount in smallest unit.

        Returns:
            dict: Captured PaymentIntent or {'error': 'message'}.
        """
        client = self._get_stripe_client()
        params = {}
        if amount_to_capture is not None:
            params['amount_to_capture'] = int(amount_to_capture)
        _logger.info('Capturing PaymentIntent: %s (amount=%s)', payment_intent_id, amount_to_capture)
        return self._safe_call(client.v1.payment_intents.capture, payment_intent_id,
                               params if params else {})

    @api.model
    def cancel_payment_intent(self, payment_intent_id):
        """
        Cancel a PaymentIntent.

        Called when the cashier cancels the payment or a timeout occurs.
        Safe to call on already-cancelled intents (returns error which is ignored).

        Returns:
            dict: {'success': True} or {'error': 'message'}.
        """
        client = self._get_stripe_client()
        _logger.info('Cancelling PaymentIntent: %s', payment_intent_id)
        result = self._safe_call(client.v1.payment_intents.cancel, payment_intent_id, {})
        if result.get('error'):
            return result
        return {'success': True, 'status': result.get('status')}

    # ------------------------------------------------------------------
    # Reader / Terminal
    # ------------------------------------------------------------------

    @api.model
    def process_reader_payment(self, payment_intent_id, reader_id=None):
        """
        Instruct a Stripe Terminal reader to collect a card-present payment.

        Works for ALL reader types:
          - BBPOS WisePOS E, Stripe Reader S700 (countertop)
          - BBPOS Chipper 2X BT, Stripe Reader M2 (Bluetooth mobile)
          - Tap to Pay on iPhone (no hardware, iOS SDK)
          - Tap to Pay on Android (no hardware, Android SDK)

        In TEST mode: auto-simulates the card tap via Stripe test helper.
        In LIVE mode: instructs reader and waits for physical card tap.

        Args:
            payment_intent_id (str): The PaymentIntent to collect.
            reader_id (str):         Reader ID (tmr_...). Falls back to config if blank.

        Returns:
            dict: {'reader_id': ..., 'status': ...} or {'error': 'message'}.
        """
        client = self._get_stripe_client()

        if not reader_id:
            reader_id = self._get_param('reader_id', '')
        if not reader_id:
            return {'error': _(
                'No Stripe Reader ID configured.\n'
                'Go to Settings → Stripe Terminal and enter your Reader ID (tmr_...).\n'
                'Or use the Setup Wizard to create a simulated reader for testing.'
            )}

        _logger.info('Instructing reader %s to process PaymentIntent %s', reader_id, payment_intent_id)

        # Step 1: Tell the reader to process the PaymentIntent
        process_result = self._safe_call(
            client.v1.terminal.readers.process_payment_intent,
            reader_id,
            {'payment_intent': payment_intent_id},
        )
        if process_result.get('error'):
            _logger.error('process_payment_intent failed: %s', process_result['error'])
            return process_result

        # Step 2 (TEST MODE only): Simulate the card tap automatically
        if self._is_test_mode():
            _logger.info('[TEST] Simulating card tap on reader %s', reader_id)
            sim_result = self._safe_call(
                client.v1.test_helpers.terminal.readers.present_payment_method,
                reader_id,
            )
            if sim_result.get('error'):
                _logger.warning('[TEST] Simulation failed (non-fatal): %s', sim_result['error'])
                return {
                    'reader_id': reader_id,
                    'status': 'simulated',
                    'warning': sim_result['error'],
                }
            _logger.info('[TEST] Card tap simulated. Reader status: %s', sim_result.get('status'))
            return {'reader_id': reader_id, 'status': sim_result.get('status', 'simulated')}

        # LIVE MODE: Customer taps card/phone — no further server call needed here
        _logger.info('[LIVE] Reader %s instructed. Waiting for customer tap.', reader_id)
        return {'reader_id': reader_id, 'status': process_result.get('status', 'in_progress')}

    # Backwards-compatible alias
    @api.model
    def simulate_reader_payment(self, payment_intent_id, reader_id=None):
        return self.process_reader_payment(payment_intent_id, reader_id=reader_id)

    # ------------------------------------------------------------------
    # Refunds
    # ------------------------------------------------------------------

    @api.model
    def create_refund(self, charge_id=None, payment_intent_id=None,
                      amount=None, reason='requested_by_customer', metadata=None):
        """
        Create a Stripe Refund for a captured payment.

        Can refund by charge ID or PaymentIntent ID (Stripe resolves the charge).
        Supports full and partial refunds.

        Args:
            charge_id (str):          Stripe Charge ID (ch_...). Preferred.
            payment_intent_id (str):  Stripe PaymentIntent ID (pi_...). Used if no charge_id.
            amount (int|None):        Amount to refund in smallest currency unit (pence).
                                      None = full refund.
            reason (str):             'requested_by_customer', 'duplicate', or 'fraudulent'.
            metadata (dict):          Key-value pairs attached to the Refund.

        Returns:
            dict: Stripe Refund object or {'error': 'message'}.

        Stripe docs: https://stripe.com/docs/api/refunds/create
        """
        client = self._get_stripe_client()
        metadata = metadata or {}

        params = {
            'reason':   reason,
            'metadata': metadata,
        }
        if charge_id:
            params['charge'] = charge_id
        elif payment_intent_id:
            params['payment_intent'] = payment_intent_id
        else:
            return {'error': _('Either charge_id or payment_intent_id is required to create a refund.')}

        if amount is not None:
            params['amount'] = int(amount)

        refund_type = 'partial' if amount is not None else 'full'
        _logger.info(
            'Creating %s refund: charge=%s pi=%s amount=%s reason=%s',
            refund_type, charge_id, payment_intent_id, amount, reason
        )

        result = self._safe_call(client.v1.refunds.create, params)

        if not result.get('error'):
            _logger.info(
                'Refund created: %s | status=%s | amount=%s',
                result.get('id'), result.get('status'), result.get('amount')
            )
        else:
            _logger.error('Refund failed: %s', result['error'])

        return result

    @api.model
    def retrieve_refund(self, refund_id):
        """Retrieve a Stripe Refund by ID."""
        client = self._get_stripe_client()
        return self._safe_call(client.v1.refunds.retrieve, refund_id)

    @api.model
    def list_refunds(self, charge_id=None, payment_intent_id=None, limit=10):
        """List refunds for a charge or payment intent."""
        client = self._get_stripe_client()
        params = {'limit': limit}
        if charge_id:
            params['charge'] = charge_id
        elif payment_intent_id:
            params['payment_intent'] = payment_intent_id
        result = self._safe_call(client.v1.refunds.list, params)
        if result.get('error'):
            return result
        return {'refunds': result.get('data', []), 'has_more': result.get('has_more', False)}

    @api.model
    def list_readers(self, location_id=None):
        """List all Terminal readers for a location."""
        client = self._get_stripe_client()
        params = {}
        if location_id:
            params['location'] = location_id
        result = self._safe_call(client.v1.terminal.readers.list, params if params else {})
        if result.get('error'):
            return result
        return {'readers': result.get('data', [])}

    @api.model
    def create_simulated_reader(self, location_id, label='Odoo Simulated Reader'):
        """
        Create a simulated Stripe Terminal reader for testing.

        Only works with test API keys. The created reader appears in the
        Stripe Dashboard (test mode) under Terminal → Readers.

        Args:
            location_id (str): The Terminal Location ID (tml_...).
            label (str):       A friendly name for this simulated reader.

        Returns:
            dict: Stripe Reader object or {'error': 'message'}.
        """
        client = self._get_stripe_client()
        if not self._is_test_mode():
            return {'error': _('Simulated readers can only be created in Test Mode.')}
        _logger.info('Creating simulated reader at location %s', location_id)
        return self._safe_call(
            client.v1.terminal.readers.create,
            {
                'registration_code': 'simulated-wpe',
                'label': label,
                'location': location_id,
            },
        )
