# -*- coding: utf-8 -*-
"""
Stripe refund wizard.

For backend-only Stripe Terminal payments this keeps the simple amount-based
refund flow. For POS-linked payments it switches to an order-line based flow
that creates a real POS refund order and payment before synchronizing the
Stripe refund.
"""

import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_is_zero

_logger = logging.getLogger(__name__)


class StripeRefundWizard(models.TransientModel):
    _name = 'stripe.refund.wizard'
    _description = 'Stripe Terminal Refund Wizard'

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
    use_pos_refund_flow = fields.Boolean(string='Use POS Refund Flow', readonly=True)
    pos_order_id = fields.Many2one('pos.order', string='POS Order', readonly=True)

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
    selected_line_total = fields.Float(
        string='Selected POS Total',
        digits=(16, 2),
        compute='_compute_pos_selection_amounts',
        readonly=True,
    )
    selected_refund_amount = fields.Float(
        string='Actual Refund Amount',
        digits=(16, 2),
        compute='_compute_pos_selection_amounts',
        readonly=True,
        help='The amount that will be posted to the POS refund order and refunded via Stripe.',
    )
    refund_line_ids = fields.One2many(
        'stripe.refund.wizard.line',
        'wizard_id',
        string='POS Refund Lines',
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

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        payment_id = values.get('payment_id') or self.env.context.get('default_payment_id')
        if not payment_id:
            return values

        payment = self.env['stripe.terminal.payment'].browse(payment_id)
        pos_order = payment._get_linked_pos_order()
        if payment.source == 'pos' and pos_order:
            values.update({
                'use_pos_refund_flow': True,
                'pos_order_id': pos_order.id,
                'refund_line_ids': self._get_default_pos_refund_line_commands(
                    pos_order,
                    values.get('max_refund', payment.amount - payment.refund_amount),
                ),
            })
        return values

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for wizard in records:
            wizard._prepare_pos_refund_context()
            wizard._ensure_pos_refund_lines()
            if not wizard.use_pos_refund_flow and wizard.refund_type == 'full':
                wizard.refund_amount = wizard.max_refund
        return records

    def _prepare_pos_refund_context(self):
        for wizard in self:
            if wizard.use_pos_refund_flow or not wizard.payment_id:
                continue
            pos_order = wizard.payment_id._get_linked_pos_order()
            if wizard.payment_id.source == 'pos' and pos_order:
                wizard.write({
                    'use_pos_refund_flow': True,
                    'pos_order_id': pos_order.id,
                })

    @api.model
    def _get_default_pos_refund_line_commands(self, pos_order, max_refund):
        refundable_lines = pos_order.lines.filtered(
            lambda line: (line.qty - line.refunded_qty) > 0
        )
        if not refundable_lines:
            return []

        total_remaining = sum(
            self._compute_line_total(line, line.qty - line.refunded_qty)
            for line in refundable_lines
        )
        default_full = total_remaining <= (max_refund or 0.0) + 0.001

        commands = []
        for original_line in refundable_lines:
            max_qty = original_line.qty - original_line.refunded_qty
            commands.append((0, 0, {
                'original_line_id': original_line.id,
                'refund_qty': max_qty if default_full else 0.0,
            }))
        return commands

    def _compute_line_total(self, original_line, qty):
        if not original_line or qty <= 0:
            return 0.0

        taxes = original_line.tax_ids_after_fiscal_position or original_line.tax_ids
        price = original_line.price_unit * (1 - (original_line.discount or 0.0) / 100.0)
        totals = taxes.compute_all(
            price,
            original_line.order_id.pricelist_id.currency_id,
            qty,
            product=original_line.product_id,
            partner=original_line.order_id.partner_id,
        )
        return abs(totals['total_included'])

    def _is_initial_full_order_refund(self):
        self.ensure_one()
        if not self.use_pos_refund_flow or not self.pos_order_id or not self.refund_line_ids:
            return False
        if any(not float_is_zero(line.original_line_id.refunded_qty, precision_rounding=line.original_line_id.product_uom_id.rounding or 0.01)
               for line in self.refund_line_ids):
            return False
        return all(
            float_is_zero(
                line.refund_qty - line.max_refundable_qty,
                precision_rounding=line.original_line_id.product_uom_id.rounding or 0.01,
            )
            for line in self.refund_line_ids
        )

    def _get_selected_pos_line_quantities(self):
        self.ensure_one()
        line_quantities = {}
        for line in self.refund_line_ids:
            if float_is_zero(
                line.refund_qty,
                precision_rounding=line.original_line_id.product_uom_id.rounding or 0.01,
            ):
                continue
            line_quantities[line.original_line_id.id] = line.refund_qty
        return line_quantities

    def _ensure_pos_refund_lines(self):
        for wizard in self:
            if not wizard.use_pos_refund_flow or wizard.refund_line_ids or not wizard.pos_order_id:
                continue

            refundable_lines = wizard.pos_order_id.lines.filtered(
                lambda line: (line.qty - line.refunded_qty) > 0
            )
            if not refundable_lines:
                continue
            commands = wizard._get_default_pos_refund_line_commands(
                wizard.pos_order_id,
                wizard.max_refund,
            )
            wizard.with_context(skip_pos_refund_validation=True).write({
                'refund_line_ids': commands,
            })

    @api.depends(
        'use_pos_refund_flow',
        'refund_line_ids.refund_qty',
        'refund_line_ids.max_refundable_qty',
        'refund_line_ids.original_line_id.price_unit',
        'refund_line_ids.original_line_id.discount',
        'refund_line_ids.original_line_id.tax_ids',
        'refund_line_ids.original_line_id.refunded_qty',
        'max_refund',
    )
    def _compute_pos_selection_amounts(self):
        for wizard in self:
            if not wizard.use_pos_refund_flow:
                wizard.selected_line_total = 0.0
                wizard.selected_refund_amount = 0.0
                continue

            selected_total = sum(line.refund_total for line in wizard.refund_line_ids)
            wizard.selected_line_total = selected_total
            if wizard._is_initial_full_order_refund():
                wizard.selected_refund_amount = wizard.max_refund
            else:
                wizard.selected_refund_amount = selected_total

    @api.onchange('refund_type', 'max_refund')
    def _onchange_refund_type(self):
        if self.use_pos_refund_flow:
            return
        if self.refund_type == 'full':
            self.refund_amount = self.max_refund
        elif self.refund_type == 'partial' and not self.refund_amount:
            self.refund_amount = self.max_refund

    @api.constrains('refund_amount', 'max_refund', 'refund_line_ids', 'refund_line_ids.refund_qty')
    def _check_refund_amount(self):
        for wizard in self:
            if wizard.env.context.get('skip_pos_refund_validation'):
                continue
            if wizard.use_pos_refund_flow:
                if not wizard.refund_line_ids:
                    continue
                selected_lines = wizard._get_selected_pos_line_quantities()
                if not selected_lines:
                    raise ValidationError(_('Select at least one POS line to refund.'))
                if wizard.selected_refund_amount <= 0:
                    raise ValidationError(_('The selected POS refund amount must be greater than zero.'))
                if wizard.selected_refund_amount > wizard.max_refund + 0.001:
                    raise ValidationError(_(
                        'The selected POS refund amount (%(amount)s) cannot exceed the remaining Stripe amount (%(max)s).',
                        amount=wizard.selected_refund_amount,
                        max=wizard.max_refund,
                    ))
                continue

            if wizard.refund_amount <= 0:
                raise ValidationError(_('Refund amount must be greater than zero.'))
            if wizard.refund_amount > wizard.max_refund + 0.001:
                raise ValidationError(_(
                    'Refund amount (%(amount)s) cannot exceed the maximum refundable amount (%(max)s).',
                    amount=wizard.refund_amount,
                    max=wizard.max_refund,
                ))

    def action_confirm_refund(self):
        self.ensure_one()
        if not self.payment_id:
            raise UserError(_('No payment selected.'))

        if self.use_pos_refund_flow:
            result = self.payment_id.action_refund_pos_payment(
                line_quantities=self._get_selected_pos_line_quantities(),
                reason=self.reason,
                note=self.note or '',
            )
            _logger.info(
                'POS refund synchronized from Stripe Terminal payment %s via refund %s',
                self.payment_id.name,
                result.get('id'),
            )
        else:
            amount = self.refund_amount if self.refund_type == 'partial' else None
            self.payment_id.action_refund_payment(
                refund_amount=amount,
                reason=self.reason,
                note=self.note or '',
            )

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'stripe.terminal.payment',
            'res_id': self.payment_id.id,
            'view_mode': 'form',
            'target': 'current',
        }


class StripeRefundWizardLine(models.TransientModel):
    _name = 'stripe.refund.wizard.line'
    _description = 'Stripe Terminal Refund Wizard Line'

    wizard_id = fields.Many2one(
        'stripe.refund.wizard',
        string='Wizard',
        required=True,
        ondelete='cascade',
    )
    original_line_id = fields.Many2one(
        'pos.order.line',
        string='Original POS Line',
        required=True,
        readonly=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        related='wizard_id.currency_id',
        readonly=True,
    )
    product_id = fields.Many2one(
        'product.product',
        string='Product',
        related='original_line_id.product_id',
        readonly=True,
    )
    product_name = fields.Char(
        string='Description',
        related='original_line_id.full_product_name',
        readonly=True,
    )
    original_qty = fields.Float(
        string='Original Qty',
        related='original_line_id.qty',
        readonly=True,
    )
    already_refunded_qty = fields.Float(
        string='Already Refunded',
        compute='_compute_line_amounts',
        readonly=True,
    )
    max_refundable_qty = fields.Float(
        string='Refundable Qty',
        compute='_compute_line_amounts',
        readonly=True,
    )
    refund_qty = fields.Float(
        string='Refund Qty',
        digits='Product Unit of Measure',
        default=0.0,
    )
    has_tracking = fields.Boolean(
        string='Tracked',
        compute='_compute_line_amounts',
        readonly=True,
    )
    lot_names = fields.Char(
        string='Lots / Serials',
        compute='_compute_line_amounts',
        readonly=True,
    )
    refund_total = fields.Float(
        string='Refund Total',
        digits=(16, 2),
        compute='_compute_line_amounts',
        readonly=True,
    )
    max_refund_total = fields.Float(
        string='Max Line Total',
        digits=(16, 2),
        compute='_compute_line_amounts',
        readonly=True,
    )

    @api.depends(
        'refund_qty',
        'original_line_id.qty',
        'original_line_id.refunded_qty',
        'original_line_id.pack_lot_ids',
        'original_line_id.price_unit',
        'original_line_id.discount',
        'original_line_id.tax_ids',
    )
    def _compute_line_amounts(self):
        for line in self:
            original_line = line.original_line_id
            if not original_line:
                line.already_refunded_qty = 0.0
                line.max_refundable_qty = 0.0
                line.has_tracking = False
                line.lot_names = False
                line.refund_total = 0.0
                line.max_refund_total = 0.0
                continue

            line.already_refunded_qty = original_line.refunded_qty
            line.max_refundable_qty = max(original_line.qty - original_line.refunded_qty, 0.0)
            line.has_tracking = bool(original_line.pack_lot_ids)
            line.lot_names = ', '.join(original_line.pack_lot_ids.mapped('lot_name')) or False
            line.max_refund_total = line.wizard_id._compute_line_total(original_line, line.max_refundable_qty)
            line.refund_total = line.wizard_id._compute_line_total(original_line, line.refund_qty)

    @api.constrains('refund_qty')
    def _check_refund_qty(self):
        for line in self:
            rounding = line.original_line_id.product_uom_id.rounding or 0.01
            if line.refund_qty < 0:
                raise ValidationError(_('Refund quantity cannot be negative.'))
            if line.refund_qty > line.max_refundable_qty + 0.00001:
                raise ValidationError(_(
                    'Refund quantity for "%(product)s" cannot exceed %(max)s.',
                    product=line.product_name or line.product_id.display_name,
                    max=line.max_refundable_qty,
                ))
            if line.has_tracking and not float_is_zero(
                line.refund_qty,
                precision_rounding=rounding,
            ) and not float_is_zero(
                line.refund_qty - line.max_refundable_qty,
                precision_rounding=rounding,
            ):
                raise ValidationError(_(
                    'Tracked line "%s" must be refunded with its full remaining quantity.',
                    line.product_name or line.product_id.display_name,
                ))
