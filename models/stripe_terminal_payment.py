# -*- coding: utf-8 -*-
"""
stripe_terminal_payment.py
===========================
Main model for tracking Stripe Terminal payment records in Odoo.

Each record represents one payment attempt made through Stripe Terminal.
Stores the PaymentIntent ID, amount, currency, status, and Stripe references
so that every transaction is auditable inside Odoo.

Phase 2 note: Add real reader/location linking here when hardware is added.
"""

import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class StripeTerminalPayment(models.Model):
    _name = 'stripe.terminal.payment'
    _description = 'Stripe Terminal Payment'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'
    _rec_name = 'name'

    # ── Basic Info ────────────────────────────────────────────────────────────
    name = fields.Char(
        string='Reference',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
        tracking=True,
    )
    description = fields.Char(
        string='Description',
        help='Short description for this payment (e.g. "Table 5 order", "POS Sale #123")',
    )

    # ── Amount / Currency ─────────────────────────────────────────────────────
    amount = fields.Float(
        string='Amount',
        required=True,
        digits=(16, 2),
        tracking=True,
        help='Payment amount in the selected currency.',
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        required=True,
        default=lambda self: self.env.company.currency_id,
        tracking=True,
    )
    amount_stripe = fields.Integer(
        string='Amount (Stripe units)',
        compute='_compute_amount_stripe',
        store=True,
        help='Amount in smallest currency unit (e.g. cents). Used when calling Stripe API.',
    )

    # ── Stripe References ─────────────────────────────────────────────────────
    stripe_payment_intent_id = fields.Char(
        string='Stripe PaymentIntent ID',
        readonly=True,
        copy=False,
        tracking=True,
        help='The PaymentIntent ID returned by Stripe (e.g. pi_xxxx).',
    )
    stripe_client_secret = fields.Char(
        string='Stripe Client Secret',
        readonly=True,
        copy=False,
        help='Client secret for the PaymentIntent. Used by frontend SDK. Treat as sensitive.',
    )
    stripe_reader_id = fields.Char(
        string='Stripe Reader ID',
        readonly=True,
        copy=False,
        help='The Stripe Terminal reader ID used for this payment (e.g. tmr_xxxx).',
    )
    stripe_charge_id = fields.Char(
        string='Stripe Charge ID',
        readonly=True,
        copy=False,
        tracking=True,
        help='The Charge ID returned after successful payment confirmation.',
    )
    stripe_error_message = fields.Text(
        string='Stripe Error',
        readonly=True,
        copy=False,
        help='Any error message returned by Stripe.',
    )
    source = fields.Selection(
        selection=[
            ('backend', 'Backend'),
            ('pos', 'POS'),
        ],
        string='Source',
        default='backend',
        readonly=True,
        tracking=True,
    )
    pos_payment_method_id = fields.Many2one(
        'pos.payment.method',
        string='POS Payment Method',
        readonly=True,
        copy=False,
    )
    pos_config_name = fields.Char(
        string='POS Configuration',
        readonly=True,
        copy=False,
        tracking=True,
    )
    pos_order_ref = fields.Char(
        string='POS Order Reference',
        readonly=True,
        copy=False,
        tracking=True,
    )

    # ── Status ────────────────────────────────────────────────────────────────
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('intent_created', 'Intent Created'),
            ('processing', 'Processing'),
            ('succeeded', 'Succeeded'),
            ('failed', 'Failed'),
            ('cancelled', 'Cancelled'),
            ('refunded', 'Refunded'),
            ('partially_refunded', 'Partially Refunded'),
        ],
        string='Status',
        default='draft',
        required=True,
        readonly=True,
        copy=False,
        tracking=True,
    )

    # ── Refund Fields ─────────────────────────────────────────────────────────
    stripe_refund_id = fields.Char(
        string='Stripe Refund ID',
        readonly=True,
        copy=False,
        tracking=True,
        help='The Stripe Refund ID (re_...) for the most recent refund.',
    )
    refund_amount = fields.Float(
        string='Refunded Amount',
        readonly=True,
        digits=(16, 2),
        tracking=True,
        help='Total amount refunded so far.',
    )
    refund_reason = fields.Selection(
        selection=[
            ('requested_by_customer', 'Requested by Customer'),
            ('duplicate', 'Duplicate Charge'),
            ('fraudulent', 'Fraudulent'),
        ],
        string='Refund Reason',
        readonly=True,
        tracking=True,
    )
    refund_date = fields.Datetime(
        string='Refund Date',
        readonly=True,
        tracking=True,
    )
    refund_note = fields.Text(
        string='Refund Note',
        help='Internal note explaining why the refund was issued.',
    )

    # ── Mode ──────────────────────────────────────────────────────────────────
    @api.model
    def _default_test_mode(self):
        return self.env['stripe.terminal.service']._is_test_mode()

    @api.model
    def _default_is_simulated(self):
        return self._default_test_mode()

    test_mode = fields.Boolean(
        string='Test Mode',
        default=_default_test_mode,
        readonly=True,
        help='Indicates whether this payment was made in Stripe test mode.',
    )
    is_simulated = fields.Boolean(
        string='Simulated Payment',
        default=_default_is_simulated,
        readonly=True,
        help='True when the payment was collected via Stripe simulation (not a real reader).',
    )

    # ── Relations ─────────────────────────────────────────────────────────────
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
    )
    user_id = fields.Many2one(
        'res.users',
        string='Created By',
        default=lambda self: self.env.user,
        readonly=True,
    )

    # ── Timestamps ────────────────────────────────────────────────────────────
    intent_created_at = fields.Datetime(string='Intent Created At', readonly=True)
    payment_completed_at = fields.Datetime(string='Payment Completed At', readonly=True)

    # ── Computed / Display ────────────────────────────────────────────────────
    state_color = fields.Char(compute='_compute_state_color', string='Status Color')

    # ─────────────────────────────────────────────────────────────────────────
    # Compute Methods
    # ─────────────────────────────────────────────────────────────────────────

    @api.depends('amount', 'currency_id')
    def _compute_amount_stripe(self):
        """Convert Odoo float amount to Stripe integer units (e.g. dollars → cents)."""
        zero_decimal_currencies = [
            'BIF', 'CLP', 'DJF', 'GNF', 'JPY', 'KMF', 'KRW', 'MGA',
            'PYG', 'RWF', 'UGX', 'VND', 'VUV', 'XAF', 'XOF', 'XPF',
        ]
        for rec in self:
            if rec.currency_id and rec.currency_id.name in zero_decimal_currencies:
                rec.amount_stripe = int(rec.amount)
            else:
                rec.amount_stripe = int(round(rec.amount * 100))

    @api.depends('state')
    def _compute_state_color(self):
        color_map = {
            'draft': 'secondary',
            'intent_created': 'info',
            'processing': 'warning',
            'succeeded': 'success',
            'failed': 'danger',
            'cancelled': 'secondary',
        }
        for rec in self:
            rec.state_color = color_map.get(rec.state, 'secondary')

    # ─────────────────────────────────────────────────────────────────────────
    # ORM Overrides
    # ─────────────────────────────────────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'stripe.terminal.payment'
                ) or _('New')
        return super().create(vals_list)

    @api.model
    def get_by_payment_intent(self, payment_intent_id):
        return self.sudo().search([
            ('stripe_payment_intent_id', '=', payment_intent_id)
        ], limit=1)

    @api.model
    def _build_pos_description(self, payment_method, pos_payload=None):
        pos_payload = pos_payload or {}
        parts = [
            pos_payload.get('order_name') or pos_payload.get('order_uid'),
            pos_payload.get('pos_config_name'),
            payment_method.name if payment_method else '',
        ]
        parts = [part for part in parts if part]
        return ' / '.join(parts) or _('POS Stripe Terminal Payment')

    @api.model
    def create_or_update_from_pos_payment_intent(
        self, payment_method, amount, currency_rec, intent_data, pos_payload=None, reader_id=None
    ):
        pos_payload = pos_payload or {}
        record = self.get_by_payment_intent(intent_data.get('id'))
        vals = {
            'description': self._build_pos_description(payment_method, pos_payload=pos_payload),
            'amount': amount,
            'currency_id': currency_rec.id,
            'stripe_payment_intent_id': intent_data.get('id'),
            'stripe_client_secret': intent_data.get('client_secret'),
            'stripe_reader_id': reader_id or False,
            'state': 'intent_created',
            'intent_created_at': fields.Datetime.now(),
            'payment_completed_at': False,
            'stripe_error_message': False,
            'test_mode': self._default_test_mode(),
            'is_simulated': self._default_is_simulated(),
            'source': 'pos',
            'pos_payment_method_id': payment_method.id if payment_method else False,
            'pos_config_name': pos_payload.get('pos_config_name') or False,
            'pos_order_ref': (
                pos_payload.get('order_name')
                or pos_payload.get('order_uid')
                or False
            ),
            'company_id': (payment_method.company_id or self.env.company).id,
            'user_id': self.env.user.id,
        }
        if record:
            record.write(vals)
        else:
            record = self.sudo().create(vals)
            record.message_post(body=_(
                'POS payment created from <b>%s</b> using <b>%s</b>.<br/>'
                'PaymentIntent: <b>%s</b>'
            ) % (
                pos_payload.get('pos_config_name') or 'POS',
                payment_method.name if payment_method else 'Stripe Terminal',
                intent_data.get('id') or '—',
            ))
        return record

    def apply_pos_status_update(
        self, state=None, reader_id=None, charge_id=None, error_message=None, note=None,
        payment_completed=False
    ):
        self.ensure_one()
        vals = {}
        if state:
            vals['state'] = state
        if reader_id:
            vals['stripe_reader_id'] = reader_id
        if charge_id:
            vals['stripe_charge_id'] = charge_id
        if error_message is not None:
            vals['stripe_error_message'] = error_message
        if payment_completed:
            vals['payment_completed_at'] = fields.Datetime.now()
        if vals:
            self.sudo().write(vals)
        if note:
            self.message_post(body=note)
        return self

    def register_external_refund(self, refund_data, refund_amount=None,
                                 reason='requested_by_customer', note=''):
        """Update this record after a refund already succeeded elsewhere."""
        self.ensure_one()

        refund_amount_float = (refund_data.get('amount') or 0) / 100.0
        total_refunded = self.refund_amount + refund_amount_float
        is_full_refund = abs(total_refunded - self.amount) < 0.01

        self.write({
            'stripe_refund_id': refund_data.get('id'),
            'refund_amount': total_refunded,
            'refund_reason': reason,
            'refund_date': fields.Datetime.now(),
            'refund_note': note or self.refund_note,
            'state': 'refunded' if is_full_refund else 'partially_refunded',
        })

        refund_label = 'FULL' if is_full_refund else 'PARTIAL'
        self.message_post(body=_(
            '💸 %s REFUND recorded from POS: <b>%s %s</b>\n'
            'Stripe Refund ID: <b>%s</b>\n'
            'Reason: %s\n'
            'Note: %s'
        ) % (
            refund_label,
            self.currency_id.symbol or '£',
            refund_amount_float,
            refund_data.get('id'),
            reason,
            note or '—',
        ))
        return self

    # ─────────────────────────────────────────────────────────────────────────
    # Business Logic / Action Methods
    # ─────────────────────────────────────────────────────────────────────────

    def action_create_payment_intent(self):
        """
        Step 1: Create a Stripe PaymentIntent for card-present payment.
        Calls Stripe API and stores the returned intent ID and client secret.
        """
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(_('Payment Intent can only be created from Draft state.'))
        if self.amount <= 0:
            raise UserError(_('Amount must be greater than zero.'))

        # Use the record's currency (e.g. GBP for UK) — never fall back to USD
        currency_code = (self.currency_id.name or self.env.company.currency_id.name or 'GBP').lower()

        service = self.env['stripe.terminal.service']
        result = service.create_payment_intent(
            amount=self.amount_stripe,
            currency=currency_code,
            description=self.description or self.name,
            metadata={'odoo_payment_ref': self.name, 'odoo_uid': str(self.env.uid)},
        )

        if result.get('error'):
            self.write({
                'state': 'failed',
                'stripe_error_message': result['error'],
            })
            self.message_post(body=_('❌ PaymentIntent creation failed: %s') % result['error'])
            raise UserError(_('Stripe error: %s') % result['error'])

        is_test_mode = service._is_test_mode()

        self.write({
            'stripe_payment_intent_id': result['id'],
            'stripe_client_secret': result['client_secret'],
            'state': 'intent_created',
            'intent_created_at': fields.Datetime.now(),
            'test_mode': is_test_mode,
            'is_simulated': is_test_mode,  # Only simulated in test mode
        })
        self.message_post(
            body=_('✅ PaymentIntent created: <b>%s</b>') % result['id']
        )
        _logger.info('Stripe PaymentIntent created: %s for record %s', result['id'], self.name)

    def action_simulate_payment(self):
        """
        Step 2: Instruct the Stripe Terminal reader to collect the card-present payment.

        In test mode: uses Stripe's simulation API to mimic a card tap automatically.
        In live mode: instructs the physical reader / Tap to Pay device; the customer
                      then taps their card, Apple Pay (iOS), or Google Pay (Android).

        Supports all contactless payment methods accepted in the UK:
          - Physical contactless cards (Visa, Mastercard, Amex, Maestro)
          - Apple Pay on iPhone (Tap to Pay on iPhone)
          - Google Pay on Android (Tap to Pay on Android)
          - Any NFC-enabled payment device
        """
        self.ensure_one()
        if self.state != 'intent_created':
            raise UserError(_('Please create a Payment Intent first.'))
        if not self.stripe_payment_intent_id:
            raise UserError(_('No Stripe PaymentIntent ID found.'))

        service = self.env['stripe.terminal.service']
        reader_id = service._get_resolved_reader_id(self.stripe_reader_id)
        is_test_mode = service._is_test_mode()
        result = service.process_reader_payment(
            payment_intent_id=self.stripe_payment_intent_id,
            reader_id=reader_id,
        )

        if result.get('error'):
            self.write({
                'state': 'failed',
                'stripe_error_message': result['error'],
            })
            self.message_post(body=_('❌ Reader payment failed: %s') % result['error'])
            raise UserError(_('Stripe error: %s') % result['error'])

        self.write({
            'stripe_reader_id': result.get('reader_id', reader_id),
            'state': 'processing',
        })

        if is_test_mode:
            self.message_post(
                body=_('📱 [Test Mode] Payment simulation initiated. Reader is processing the payment.')
            )
            _logger.info('[TEST MODE] Stripe payment simulation started for intent: %s', self.stripe_payment_intent_id)
        else:
            self.message_post(
                body=_(
                    '📱 Reader instructed. Please tap your card, Apple Pay (iPhone) or '
                    'Google Pay (Android) on the reader now.'
                )
            )
            _logger.info('[LIVE] Stripe reader instructed for intent: %s', self.stripe_payment_intent_id)

    def action_confirm_payment(self):
        """
        Step 3: Capture the PaymentIntent after the reader has processed it.

        Stripe Terminal flow:
          - After process_reader_payment (step 2), PI status = 'requires_capture'
          - We must call CAPTURE (not confirm) to finalise and charge the card
          - confirm() is only for online payments — NOT for Terminal card-present payments

        Stripe Terminal docs: https://stripe.com/docs/terminal/payments/collect-payment
        """
        self.ensure_one()
        if self.state not in ('intent_created', 'processing'):
            raise UserError(_('Payment can only be confirmed when in Intent Created or Processing state.'))
        if not self.stripe_payment_intent_id:
            raise UserError(_('No Stripe PaymentIntent ID found.'))

        service = self.env['stripe.terminal.service']

        # Step 1: Check current PI status — it may already be succeeded (auto-capture)
        pi = service.retrieve_payment_intent(self.stripe_payment_intent_id)
        if pi.get('error'):
            raise UserError(_('Could not retrieve PaymentIntent: %s') % pi['error'])

        stripe_status = pi.get('status', '')
        _logger.info('PaymentIntent %s status before capture: %s',
                     self.stripe_payment_intent_id, stripe_status)

        if stripe_status == 'succeeded':
            # Already captured (auto-capture or webhook already processed)
            charge_id = pi.get('latest_charge', '')
            self._mark_succeeded(charge_id)
            return

        if stripe_status == 'requires_capture':
            # Standard Terminal flow — capture the authorised payment
            result = service.capture_payment_intent(self.stripe_payment_intent_id)

            if result.get('error'):
                self.write({
                    'state': 'failed',
                    'stripe_error_message': result['error'],
                })
                self.message_post(body=_('❌ Payment capture failed: %s') % result['error'])
                raise UserError(_('Stripe capture error: %s') % result['error'])

            if result.get('status') == 'succeeded':
                charge_id = result.get('latest_charge', '')
                self._mark_succeeded(charge_id)
                return

        if stripe_status in ('requires_confirmation', 'requires_action'):
            # Fallback — try confirm (for non-Terminal flows)
            result = service.confirm_payment_intent(self.stripe_payment_intent_id)
            if result.get('error'):
                self.write({'state': 'failed', 'stripe_error_message': result['error']})
                self.message_post(body=_('❌ Payment confirmation failed: %s') % result['error'])
                raise UserError(_('Stripe confirmation error: %s') % result['error'])
            if result.get('status') == 'succeeded':
                self._mark_succeeded(result.get('latest_charge', ''))
                return

        if stripe_status in ('requires_payment_method', 'canceled'):
            raise UserError(_(
                'Payment cannot be captured — Stripe status is "%s".\n\n'
                'This means the reader did not complete the card tap.\n'
                'Please go back to Step 2 and try again.'
            ) % stripe_status)

        # Unknown status
        _logger.warning('Unexpected PI status after capture attempt: %s', stripe_status)
        self.write({
            'state': 'failed',
            'stripe_error_message': _('Unexpected Stripe status: %s') % stripe_status,
        })
        self.message_post(body=_('⚠️ Unexpected payment status: <b>%s</b>') % stripe_status)

    def _mark_succeeded(self, charge_id=''):
        """Mark this payment record as succeeded and post a success message."""
        self.write({
            'state': 'succeeded',
            'stripe_charge_id': charge_id or self.stripe_charge_id,
            'payment_completed_at': fields.Datetime.now(),
            'stripe_error_message': False,
        })
        self.message_post(
            body=_('✅ Payment <b>SUCCEEDED</b>. Charge ID: <b>%s</b>') % (charge_id or '—')
        )
        _logger.info('Stripe payment succeeded. Intent: %s, Charge: %s',
                     self.stripe_payment_intent_id, charge_id)

    def action_cancel_payment(self):
        """Cancel the PaymentIntent with Stripe and mark as cancelled in Odoo."""
        self.ensure_one()
        if self.state in ('succeeded', 'cancelled'):
            raise UserError(_('Cannot cancel a succeeded or already cancelled payment.'))

        service = self.env['stripe.terminal.service']
        reader_id = service._get_resolved_reader_id(self.stripe_reader_id)
        if reader_id:
            reader_result = service.cancel_reader_action(reader_id=reader_id)
            if reader_result.get('error'):
                _logger.warning(
                    'Could not cancel reader action for backend payment %s on reader %s: %s',
                    self.name, reader_id, reader_result['error']
                )

        if self.stripe_payment_intent_id:
            result = service.cancel_payment_intent(
                payment_intent_id=self.stripe_payment_intent_id,
            )
            if result.get('error'):
                raise UserError(_('Stripe cancel error: %s') % result['error'])

        self.write({'state': 'cancelled'})
        self.message_post(body=_('🚫 Payment cancelled.'))
        _logger.info('Stripe payment cancelled for record: %s', self.name)

    def action_reset_to_draft(self):
        """Reset payment to draft for retry (only allowed in failed/cancelled state)."""
        self.ensure_one()
        if self.state not in ('failed', 'cancelled'):
            raise UserError(_('Only failed or cancelled payments can be reset to draft.'))
        self.write({
            'state': 'draft',
            'stripe_payment_intent_id': False,
            'stripe_client_secret': False,
            'stripe_reader_id': False,
            'stripe_charge_id': False,
            'stripe_error_message': False,
            'intent_created_at': False,
            'payment_completed_at': False,
        })
        self.message_post(body=_('🔄 Payment reset to Draft for retry.'))

    def action_refund_payment(self, refund_amount=None, reason='requested_by_customer', note=''):
        """
        Issue a full or partial refund for a succeeded payment.

        Calls Stripe Refunds API and updates the Odoo record.
        Can be triggered from the backend form or programmatically.

        Args:
            refund_amount (float|None): Amount to refund (None = full refund).
            reason (str):               'requested_by_customer', 'duplicate', 'fraudulent'.
            note (str):                 Internal note stored on the record.

        Returns:
            dict: Stripe Refund object or raises UserError on failure.
        """
        self.ensure_one()

        if self.state not in ('succeeded', 'partially_refunded'):
            raise UserError(_(
                'Refunds can only be issued for succeeded or partially refunded payments.\n'
                'Current status: %s'
            ) % self.state)

        if not self.stripe_payment_intent_id:
            raise UserError(_('No Stripe PaymentIntent ID found on this record.'))

        # Determine refund amount in Stripe units
        svc = self.env['stripe.terminal.service']
        amount_int = None
        if refund_amount is not None and refund_amount > 0:
            amount_int = svc._amount_to_stripe_int(refund_amount, self.currency_id.name or 'GBP')
        else:
            # Full refund
            refund_amount = self.amount - self.refund_amount

        _logger.info(
            'Refunding payment %s: amount=%s %s, reason=%s',
            self.name, refund_amount, self.currency_id.name, reason
        )

        result = svc.create_refund(
            payment_intent_id=self.stripe_payment_intent_id,
            amount=amount_int,
            reason=reason,
            metadata={
                'odoo_payment_ref': self.name,
                'odoo_user': self.env.user.name,
                'odoo_note': note or '',
            },
        )

        if result.get('error'):
            self.message_post(body=_('❌ Refund failed: %s') % result['error'])
            raise UserError(_('Stripe refund error: %s') % result['error'])

        # Calculate total refunded
        refund_amount_float = (result.get('amount') or 0) / 100.0
        total_refunded = self.refund_amount + refund_amount_float
        is_full_refund = abs(total_refunded - self.amount) < 0.01

        self.write({
            'stripe_refund_id': result.get('id'),
            'refund_amount': total_refunded,
            'refund_reason': reason,
            'refund_date': fields.Datetime.now(),
            'refund_note': note or self.refund_note,
            'state': 'refunded' if is_full_refund else 'partially_refunded',
        })

        refund_label = 'FULL' if is_full_refund else 'PARTIAL'
        self.message_post(body=_(
            '💸 %s REFUND issued: <b>%s %s</b>\n'
            'Stripe Refund ID: <b>%s</b>\n'
            'Reason: %s\n'
            'Note: %s'
        ) % (
            refund_label,
            self.currency_id.symbol or '£',
            refund_amount_float,
            result.get('id'),
            reason,
            note or '—',
        ))
        _logger.info('Refund %s issued for payment %s: %s', result.get('id'), self.name, refund_label)
        return result

    def action_open_refund_wizard(self):
        """Open the refund wizard dialog from the form view."""
        self.ensure_one()
        if self.state not in ('succeeded', 'partially_refunded'):
            raise UserError(_(
                'Only succeeded or partially refunded payments can be refunded.'
            ))
        remaining = self.amount - self.refund_amount
        return {
            'name': _('Issue Refund'),
            'type': 'ir.actions.act_window',
            'res_model': 'stripe.refund.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_payment_id': self.id,
                'default_payment_name': self.name,
                'default_original_amount': self.amount,
                'default_already_refunded': self.refund_amount,
                'default_refund_amount': remaining,
                'default_currency_id': self.currency_id.id,
                'default_max_refund': remaining,
            },
        }

    def action_open_stripe_dashboard(self):
        """Open the Stripe Dashboard for this PaymentIntent."""
        self.ensure_one()
        if not self.stripe_payment_intent_id:
            raise UserError(_('No Stripe PaymentIntent ID available.'))
        if self.test_mode:
            url = 'https://dashboard.stripe.com/test/payments/%s' % self.stripe_payment_intent_id
        else:
            url = 'https://dashboard.stripe.com/payments/%s' % self.stripe_payment_intent_id
        return {
            'type': 'ir.actions.act_url',
            'url': url,
            'target': 'new',
        }
