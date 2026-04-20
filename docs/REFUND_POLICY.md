# Stripe Terminal — Refund Guide

This guide describes the current refund behavior in `orbit_stripe_contactless_payment`.

---

## 1. Current Refund Model

Stripe Terminal refunds are driven from the backend `Stripe Terminal Payments` flow.

Use:

- `Stripe Terminal -> Payments -> All Payments`

Then open the payment and click:

- `Issue Refund`

This is the supported Stripe refund path for:

- backend-origin Stripe Terminal payments
- POS-linked Stripe Terminal payments

---

## 2. Important Difference for POS Sales

For POS-linked Stripe Terminal payments, the backend refund flow now does more than call Stripe.

It also:

- creates a real Odoo POS refund order
- creates the POS refund payment
- links the refund order/payment back to the Stripe payment record
- keeps POS totals, stock, and reporting aligned

This is why the backend refund flow is the correct one for Stripe Terminal POS sales in this module.

---

## 3. POS Screen Refund Behavior

The POS screen itself does not process the Stripe refund API for these Stripe Terminal payments.

If a cashier tries to reverse the payment from the POS payment line, the module directs them to use:

- the backend `Stripe Terminal Payments` menu
- or the Stripe Dashboard

So for Stripe Terminal refunds in this module:

- use the backend refund wizard

---

## 4. Refund Paths

### Path A — Backend refund from Stripe Terminal Payments

Recommended for all Stripe Terminal refunds.

Use when:

- the payment was created in the backend
- the payment came from POS
- you want Odoo refund sync and audit trail

### Path B — Stripe Dashboard refund

Possible, but Odoo sync depends on webhooks.

If you refund directly in Stripe Dashboard:

- Stripe processes the refund
- Odoo updates automatically only if `charge.refunded` webhook handling is configured

### Path C — Programmatic refund

Possible from Python code or service calls for controlled automation.

---

## 5. Backend Refund Flow

### For backend-origin payments

The wizard uses a simple amount-based refund flow:

- full or partial refund
- refund reason
- internal note

### For POS-linked payments

The wizard switches to a line-based POS refund flow:

- shows the linked POS order
- shows refundable order lines
- lets you choose quantities
- validates against remaining Stripe refundable amount
- creates the Odoo POS refund order/payment first
- then sends the Stripe refund

---

## 6. POS-Linked Refund Requirement

For POS-linked refunds, the same POS configuration must have an open session.

If no open session exists, Odoo cannot create the refund order.

Practical rule:

- before refunding a POS-linked Stripe payment, make sure the related POS has an open session

---

## 7. Refund Steps

### Backend-origin payment

1. Open `Stripe Terminal -> Payments -> All Payments`
2. Open a succeeded payment
3. Click `Issue Refund`
4. Choose full or partial refund
5. Confirm

### POS-linked payment

1. Open a session on the same POS config as the original sale
2. Open `Stripe Terminal -> Payments -> All Payments`
3. Open the Stripe payment linked to the POS sale
4. Click `Issue Refund`
5. Select refund quantities on the POS order lines
6. Confirm

Expected result:

- Stripe refund is created
- backend record updates
- POS refund order/payment is created

---

## 8. Refund States

Possible Stripe Terminal payment states after refunding:

- `Partially Refunded`
- `Refunded`

The record also stores:

- `Stripe Refund ID`
- `Refunded Amount`
- `Refund Reason`
- `Refund Date`
- linked POS refund orders/payments for POS-origin sales

---

## 9. Refund Receipts

After a refund exists, the payment record can print:

- `Refund`

Current behavior:

- POS-linked refunds print the latest refund receipt from the refund POS order
- backend-origin refunds print the backend thermal refund receipt

Printing is browser-based thermal HTML.

See:

- [PRINTER_SETUP_GUIDE.md](PRINTER_SETUP_GUIDE.md)

---

## 10. Dashboard Refund Sync

If refunds are made directly in Stripe Dashboard, configure webhook support so Odoo stays aligned.

Recommended event:

- `charge.refunded`

Also useful:

- `payment_intent.succeeded`
- `payment_intent.payment_failed`
- `payment_intent.canceled`
- `terminal.reader.action_failed`

See:

- [WEBHOOK_SIMULATION_GUIDE.md](WEBHOOK_SIMULATION_GUIDE.md)

---

## 11. Programmatic Example

Backend-origin example:

```python
payment = env['stripe.terminal.payment'].browse(payment_id)
payment.action_refund_payment(
    refund_amount=5.00,
    reason='requested_by_customer',
    note='Customer returned one item',
)
```

POS-linked payments should normally use the refund wizard so line selection and POS order creation stay correct.

---

## 12. Common Refund Issues

### The selected POS refund total exceeds the remaining Stripe amount

Cause:

- selected lines/quantities are worth more than the remaining Stripe refundable amount

Fix:

- reduce quantities or refund the remaining Stripe amount only

### No open POS session

Cause:

- POS-linked refund needs a live session on the original POS config

Fix:

- open the session first, then retry the backend refund

### No refund button visible

Cause:

- payment has not reached `Succeeded` or `Partially Refunded`

Fix:

- refund only succeeded Stripe Terminal payments

### Dashboard refund did not update Odoo

Cause:

- `charge.refunded` webhook not configured

Fix:

- configure webhook forwarding and webhook secret

---

## 13. Recommended Refund Policy for Staff

- cashiers should not try to reverse Stripe Terminal payments directly from the POS payment line
- managers or authorized staff should refund from `Stripe Terminal Payments`
- keep the related POS session open when refunding POS-linked sales
- print the `Refund` receipt after successful refund

---

## 14. Related Guides

- [REFUND_TEST_GUIDE.md](REFUND_TEST_GUIDE.md)
- [WEBHOOK_SIMULATION_GUIDE.md](WEBHOOK_SIMULATION_GUIDE.md)
- [PRINTER_SETUP_GUIDE.md](PRINTER_SETUP_GUIDE.md)
- [DEBUG_AND_FAQ.md](DEBUG_AND_FAQ.md)
