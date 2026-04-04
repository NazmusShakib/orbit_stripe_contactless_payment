# -*- coding: utf-8 -*-
"""
Stripe Refund Wizard
====================
A transient dialog that lets staff issue full or partial refunds
for succeeded Stripe Terminal payments directly from the backend.
"""
import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class StripeRefundWizard(models.TransientModel):
    _name = 'stripe.refund.wizard'
    _description = 'Stripe Terminal Refund Wizard'

    # ------------------------------------------------------------------
    # Fields
    # ------------------------------------------------------------------

    payment_id = fields.Many2one(
        'stripe.terminal.payment',
        string='Payment',
        required=True,
        readonly=True,
    )
    payment_name = fields.Char(string='Payment Ref', readonly=True)
    currency_id = fields.Many2one('res.currency', string='Currency', readonly=True)
    original_amount = fields.Float(string='Original Amount', readonly=True, digits=(16, 2))
    already_refunded = fields.Float(string='Already Refunded', readonly=True, digits=(16, 2))
    max_refund = fields.Float(string='Max Refundable', readonly=True, digits=(16, 2))

    refund_type = fields.Selection(
        selection=[
            ('full', 'Full Refund'),
            ('partial', 'Partial Refund'),
        ],
        string='Refund Type',
        default='full',
        required=True,
    )
    refund_amount = fields.Float(
        string='Amount to Refund',
        digits=(16, 2),
        help='Leave as-is for full refund, or enter a smaller amount for partial refund.',
    )
    reason = fields.Selection(
        selection=[
            ('requested_by_customer', 'Requested by Customer'),
            ('duplicate', 'Duplicate Charge'),
            ('fraudulent', 'Fraudulent'),
        ],
        string='Reason',
        default='requested_by_customer',
        required=True,
    )
    note = fields.Text(
        string='Internal Note',
        help='Optional note for your records (not sent to Stripe or customer).',
    )

    # ------------------------------------------------------------------
    # Onchange
    # ------------------------------------------------------------------

    @api.onchange('refund_type', 'max_refund')
    def _onchange_refund_type(self):
        if self.refund_type == 'full':
            self.refund_amount = self.max_refund
        elif self.refund_type == 'partial' and not self.refund_amount:
            self.refund_amount = self.max_refund

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    @api.constrains('refund_amount', 'max_refund')
    def _check_refund_amount(self):
        for rec in self:
            if rec.refund_amount <= 0:
                raise ValidationError(_('Refund amount must be greater than zero.'))
            if rec.refund_amount > rec.max_refund + 0.001:
                raise ValidationError(_(
                    'Refund amount (%(amount)s) cannot exceed the maximum refundable amount (%(max)s).',
                    amount=rec.refund_amount,
                    max=rec.max_refund,
                ))

    # ------------------------------------------------------------------
    # Action
    # ------------------------------------------------------------------

    def action_confirm_refund(self):
        """Issue the refund and close the wizard."""
        self.ensure_one()
        if not self.payment_id:
            raise UserError(_('No payment selected.'))

        amount = self.refund_amount if self.refund_type == 'partial' else None

        self.payment_id.action_refund_payment(
            refund_amount=amount,
            reason=self.reason,
            note=self.note or '',
        )

        # Return action to reload the payment form
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'stripe.terminal.payment',
            'res_id': self.payment_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
