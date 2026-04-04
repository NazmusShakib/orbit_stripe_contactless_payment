# -*- coding: utf-8 -*-
"""
Stripe Terminal HTTP Controllers
==================================
Provides endpoints called by:
  1. The Stripe Terminal JS SDK  (/stripe/terminal/connection_token)
  2. Stripe webhook events       (/stripe/terminal/webhook)
  3. Reader listing utility      (/stripe/terminal/readers)
"""
import json
import logging

from odoo import http, fields, _
from odoo.http import request, Response

_logger = logging.getLogger(__name__)


class StripeTerminalController(http.Controller):

    # ------------------------------------------------------------------
    # Connection Token — called by Stripe Terminal JS SDK
    # ------------------------------------------------------------------

    @http.route(
        '/stripe/terminal/connection_token',
        type='json',
        auth='user',
        methods=['POST'],
        csrf=True,
    )
    def get_connection_token(self, **kwargs):
        """
        Return a Stripe Terminal connection token for the POS JS SDK.
        Called automatically by the SDK whenever it needs a fresh token.
        Tokens are single-use — never cache or reuse.
        """
        try:
            service = request.env['stripe.terminal.service'].sudo()
            result  = service.get_connection_token()
            if result.get('error'):
                _logger.error('Connection token error: %s', result['error'])
            return result
        except Exception as e:
            _logger.exception('Unexpected error generating connection token')
            return {'error': str(e)}

    # ------------------------------------------------------------------
    # Webhook — receives real-time events from Stripe
    # ------------------------------------------------------------------

    @http.route(
        '/stripe/terminal/webhook',
        type='http',
        auth='none',
        methods=['POST'],
        csrf=False,
    )
    def stripe_webhook(self, **kwargs):
        """
        Handle Stripe webhook events for real-time payment confirmation.

        Stripe sends events to this URL when:
          - payment_intent.succeeded   → mark Odoo record as paid
          - payment_intent.payment_failed → mark as failed
          - payment_intent.canceled    → mark as cancelled
          - terminal.reader.action_failed → handle reader errors

        Configure in Stripe Dashboard → Developers → Webhooks:
          URL: https://YOUR-DOMAIN/stripe/terminal/webhook
          Events: payment_intent.succeeded, payment_intent.payment_failed,
                  payment_intent.canceled, terminal.reader.action_failed

        Security: signature is verified using the Webhook Secret from Settings.
        """
        payload    = request.httprequest.data
        sig_header = request.httprequest.headers.get('Stripe-Signature', '')

        if not payload:
            return Response('Bad Request', status=400)

        webhook_secret = request.env['ir.config_parameter'].sudo().get_param(
            'orbit_stripe_contactless_payment.webhook_secret', ''
        )

        # Verify webhook signature if secret is configured
        event = None
        if webhook_secret:
            try:
                import stripe as _stripe
                event = _stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
            except ValueError:
                _logger.warning('Stripe webhook: invalid payload (not JSON)')
                return Response('Bad Request', status=400)
            except Exception as e:
                _logger.warning('Stripe webhook signature verification failed: %s', e)
                return Response('Unauthorized', status=401)
        else:
            # No secret configured — parse without verification (not recommended for production)
            try:
                event = json.loads(payload)
                _logger.warning(
                    'Stripe webhook received WITHOUT signature verification. '
                    'Configure Webhook Secret in Settings → Stripe Terminal for production.'
                )
            except json.JSONDecodeError:
                return Response('Bad Request', status=400)

        event_type = event.get('type', 'unknown')
        event_id   = event.get('id', 'unknown')
        _logger.info('Stripe webhook: type=%s id=%s', event_type, event_id)

        try:
            intent_obj = event.get('data', {}).get('object', {})
            intent_id  = intent_obj.get('id', '')

            if event_type == 'payment_intent.succeeded' and intent_id:
                self._handle_payment_succeeded(intent_id, intent_obj)

            elif event_type == 'payment_intent.payment_failed' and intent_id:
                self._handle_payment_failed(intent_id, intent_obj)

            elif event_type == 'payment_intent.canceled' and intent_id:
                self._handle_payment_canceled(intent_id, intent_obj)

            elif event_type == 'charge.refunded':
                charge_id = intent_obj.get('id', '')
                self._handle_charge_refunded(charge_id, intent_obj)

            elif event_type == 'terminal.reader.action_failed':
                _logger.warning('Stripe reader action failed: %s', intent_obj)

        except Exception as e:
            _logger.exception('Error processing Stripe webhook event %s', event_type)
            # Return 200 anyway to prevent Stripe from retrying endlessly
            # Log the error and investigate manually

        return Response('OK', status=200)

    def _handle_payment_succeeded(self, intent_id, intent_obj):
        """Mark the corresponding Stripe Terminal Payment record as succeeded."""
        env = request.env['stripe.terminal.payment'].sudo()
        payment = env.search([('stripe_payment_intent_id', '=', intent_id)], limit=1)
        if payment and payment.state not in ('succeeded', 'cancelled'):
            payment.write({
                'state': 'succeeded',
                'stripe_error_message': False,
            })
            payment.message_post(body=_('✅ Payment confirmed via Stripe webhook.'))
            _logger.info('Webhook: marked payment %s as succeeded', payment.name)

    def _handle_payment_failed(self, intent_id, intent_obj):
        """Mark the corresponding Stripe Terminal Payment record as failed."""
        env = request.env['stripe.terminal.payment'].sudo()
        payment = env.search([('stripe_payment_intent_id', '=', intent_id)], limit=1)
        if payment and payment.state not in ('succeeded', 'cancelled'):
            error = (intent_obj.get('last_payment_error') or {}).get('message', 'Payment failed')
            payment.write({'state': 'failed', 'stripe_error_message': error})
            payment.message_post(body=_('❌ Payment failed via webhook: %s') % error)
            _logger.info('Webhook: marked payment %s as failed: %s', payment.name, error)

    def _handle_payment_canceled(self, intent_id, intent_obj):
        """Mark the corresponding Stripe Terminal Payment record as cancelled."""
        env = request.env['stripe.terminal.payment'].sudo()
        payment = env.search([('stripe_payment_intent_id', '=', intent_id)], limit=1)
        if payment and payment.state not in ('succeeded',):
            payment.write({'state': 'cancelled'})
            payment.message_post(body=_('🚫 Payment cancelled via Stripe webhook.'))
            _logger.info('Webhook: marked payment %s as cancelled', payment.name)

    def _handle_charge_refunded(self, charge_id, charge_obj):
        """
        Handle charge.refunded webhook event.

        Stripe sends this when a refund is created (either from Odoo or from
        Stripe Dashboard). Updates the Odoo payment record automatically.
        """
        # Find payment by PaymentIntent ID (charge object has payment_intent field)
        intent_id = charge_obj.get('payment_intent', '')
        env       = request.env['stripe.terminal.payment'].sudo()
        payment   = env.search([('stripe_payment_intent_id', '=', intent_id)], limit=1) \
                 if intent_id else None

        if not payment:
            # Try by charge ID
            payment = env.search([('stripe_charge_id', '=', charge_id)], limit=1)

        if not payment:
            _logger.info(
                'Webhook charge.refunded: no Odoo payment found for charge=%s intent=%s',
                charge_id, intent_id
            )
            return

        # Get refund details from the charge
        refunds    = charge_obj.get('refunds', {}).get('data', [])
        if not refunds:
            return

        latest_refund   = refunds[-1]
        refund_id       = latest_refund.get('id', '')
        refund_amount   = (latest_refund.get('amount') or 0) / 100.0
        refund_reason   = latest_refund.get('reason') or 'requested_by_customer'

        # Calculate total refunded from all refunds
        total_refunded  = sum((r.get('amount') or 0) for r in refunds) / 100.0
        is_full_refund  = abs(total_refunded - payment.amount) < 0.01

        if payment.state not in ('refunded',):
            payment.write({
                'stripe_refund_id': refund_id,
                'refund_amount':    total_refunded,
                'refund_reason':    refund_reason if refund_reason in (
                    'requested_by_customer', 'duplicate', 'fraudulent'
                ) else 'requested_by_customer',
                'refund_date':      fields.Datetime.now(),
                'state':            'refunded' if is_full_refund else 'partially_refunded',
            })
            payment.message_post(body=_(
                '💸 Refund confirmed via Stripe webhook.\n'
                'Refund ID: %(refund_id)s | Amount: £%(amount).2f | '
                'Type: %(type)s',
                refund_id=refund_id,
                amount=refund_amount,
                type='FULL' if is_full_refund else 'PARTIAL',
            ))
            _logger.info(
                'Webhook: charge.refunded for payment %s. Refund %s £%.2f (%s)',
                payment.name, refund_id, refund_amount,
                'FULL' if is_full_refund else 'PARTIAL'
            )

    # ------------------------------------------------------------------
    # Reader listing utility
    # ------------------------------------------------------------------

    @http.route(
        '/stripe/terminal/readers',
        type='json',
        auth='user',
        methods=['POST'],
        csrf=True,
    )
    def list_readers(self, **kwargs):
        """List available Stripe Terminal readers for the configured location."""
        try:
            ICP         = request.env['ir.config_parameter'].sudo()
            location_id = ICP.get_param('orbit_stripe_contactless_payment.location_id', '')
            service     = request.env['stripe.terminal.service'].sudo()
            return service.list_readers(location_id=location_id or None)
        except Exception as e:
            _logger.exception('Error listing readers')
            return {'error': str(e)}
