# Stripe Terminal — Refund Policy & Guide

Complete guide for issuing refunds on card, Apple Pay, and Google Pay payments.

---

## How Stripe Refunds Work

When you issue a refund through this system:

1. Odoo calls the **Stripe Refunds API** — no physical reader or card tap needed
2. Stripe marks the original charge as refunded
3. The money is returned to the **customer's original payment method** automatically:
   - Card payments → refunded to the same card
   - Apple Pay → refunded to the linked card
   - Google Pay → refunded to the linked card or account
4. The customer sees the refund on their bank statement within **5–10 business days**
5. Stripe does NOT charge a refund fee (but the original processing fee is not returned)

> **Important**: Refunds are final once submitted to Stripe. You cannot reverse a refund.

---

## Refund Methods Available

### Method 1 — POS Refund (Recommended for Cashiers)

Process a refund directly from the POS screen on a completed order.

**Steps:**

1. In the POS, go to **Orders** (clock icon)
2. Find the original order → click **Return**
3. Select the items/quantities to return → confirm
4. A new negative-amount order opens
5. Click **Payment**
6. The **Card / Contactless** payment line shows the refund amount
7. Click **Validate** → the refund is processed automatically via Stripe API
8. Customer receives their money back to their original card/wallet

**What happens behind the scenes:**

- POS JS calls `send_payment_reversal()` → `orbit_stripe_refund_payment()`
- Server calls `stripe.v1.refunds.create(payment_intent=pi_...)`
- Stripe API returns Refund ID `re_...`
- POS marks the payment as **reversed**

**Note:** The POS refund requires the original `transaction_id` (PaymentIntent ID) to be stored on the payment line. This is set automatically during payment.

---

### Method 2 — Backend Refund (Recommended for Managers)

Issue a full or partial refund from the Odoo backend with full audit trail.

**Steps:**

1. Go to **Point of Sale → Stripe Terminal Payments** (or **Orbit → Stripe Terminal**)
2. Find the payment (filter by status = **Succeeded**)
3. Click the payment to open it
4. Click ** Issue Refund** button
5. A dialog opens:
   - **Refund Type**: Full or Partial
   - **Amount**: pre-filled (edit for partial)
   - **Reason**: Requested by Customer / Duplicate / Fraudulent
   - **Note**: internal note (not shown to customer)
6. Click **Issue Refund** (red button)
7. Refund is processed immediately
8. Payment status changes to **Refunded** or **Partially Refunded**
9. Full audit trail in the chatter (messages)

---

### Method 3 — Stripe Dashboard Refund

Refund directly from the Stripe Dashboard (no Odoo needed).

**Steps:**

1. Go to https://dashboard.stripe.com/payments
2. Find the charge (search by amount, date, last 4 of card)
3. Click the charge → click **Refund**
4. Enter amount (leave blank for full refund)
5. Select reason → click **Refund**

**Odoo sync:** If you have webhooks configured (`charge.refunded` event), Odoo will automatically update the payment record status. Without webhooks, you must manually update the record.

---

### Method 4 — Programmatic Refund (Developer)

Call the refund method directly from Python code:

```python
# Full refund
payment = env['stripe.terminal.payment'].browse(payment_id)
payment.action_refund_payment(
    reason='requested_by_customer',
    note='Customer returned item'
)

# Partial refund (£5.00)
payment.action_refund_payment(
    refund_amount=5.00,
    reason='requested_by_customer',
    note='Partial return of 1 item'
)

# Via service layer directly
env['stripe.terminal.service'].create_refund(
    payment_intent_id='pi_3TF...',
    amount=500,  # pence
    reason='requested_by_customer',
)
```

---

## Refund Types

### Full Refund

- Returns the complete original payment amount
- Payment status → **Refunded**
- Cannot refund again after this

### Partial Refund

- Returns a portion of the original amount
- Payment status → **Partially Refunded**
- Can issue multiple partial refunds up to the original total
- Example: Order = £50.00 → refund £20.00 → status = Partially Refunded → refund £30.00 → status = Refunded

---

## Refund Reasons

| Reason                    | When to use                                               |
| ------------------------- | --------------------------------------------------------- |
| **Requested by Customer** | Customer changed mind, returned item, didn't want product |
| **Duplicate**             | Payment was charged twice by mistake                      |
| **Fraudulent**            | Unauthorised payment — customer didn't make the purchase  |

> Choosing **Fraudulent** adds the card to Stripe Radar's block list.

---

## Refund Timeline

| Payment Method           | Refund Timeline         |
| ------------------------ | ----------------------- |
| Visa / Mastercard credit | 5–10 business days      |
| Visa / Mastercard debit  | 2–5 business days       |
| Amex                     | 5–7 business days       |
| Apple Pay                | Same as underlying card |
| Google Pay               | Same as underlying card |
| Samsung Pay              | Same as underlying card |

---

## Refund Limits & Rules

| Rule                       | Detail                                             |
| -------------------------- | -------------------------------------------------- |
| Maximum refund             | Equal to original payment amount                   |
| Minimum refund             | £0.50 (Stripe minimum)                             |
| Refund window              | Up to **180 days** after payment (Stripe limit)    |
| Multiple partial refunds   | Allowed up to original total                       |
| Refund after refund        | Cannot refund more than original                   |
| Refund a failed payment    | Not possible                                       |
| Refund a cancelled payment | Not possible                                       |
| Processing fee returned    | Stripe does not return the original processing fee |

---

## Webhook Auto-Update (Recommended)

If you configure the `charge.refunded` webhook event, Odoo will automatically update payment records whenever a refund is issued — even if the refund was done via Stripe Dashboard.

**Add to your webhook events:**

```
charge.refunded
```

**Full webhook event list for complete coverage:**

```
payment_intent.succeeded
payment_intent.payment_failed
payment_intent.canceled
charge.refunded
terminal.reader.action_failed
```

**Setup:**

1. Stripe Dashboard → Developers → Webhooks → your endpoint → Edit → add `charge.refunded`
2. Or create a new endpoint:
   - URL: `https://YOUR-DOMAIN/stripe/terminal/webhook`
   - Events: all of the above

**Test with Stripe CLI:**

```bash
stripe trigger charge.refunded
```

---

## Simulate a Refund in Test Mode

Test the full refund flow without real money:

### Via POS (test mode):

1. Take a test payment (simulated reader)
2. Go to Orders → Return the order
3. Validate the refund payment → it calls Stripe refund API with test keys
4. Check Stripe Dashboard (test mode) → Payments → charge → Refunds tab ✅

### Via Backend:

1. Go to Stripe Terminal Payments → find a Succeeded payment
2. Click **Issue Refund** → Issue Refund
3. Check the chatter for the Stripe Refund ID (`re_...`)
4. Verify in Stripe Dashboard (test) → Payments

### Via Stripe CLI:

```bash
# After taking a test payment, find the PaymentIntent ID from the payment record
# Then create a refund manually:
stripe refunds create -d payment_intent=pi_3TF... -d amount=500
```

---

## Console Logs During POS Refund

When a refund is processed via POS, you'll see in browser console (F12):

```
[OrbitStripe] ━━━ REFUND FLOW START ━━━
[OrbitStripe] transaction_id (PaymentIntent): pi_3TFrrYK4sPO78s...
[OrbitStripe] Refund amount: 10
[OrbitStripe] → RPC Request: orbit_stripe_refund_payment {"payment_intent_id": "pi_3TF...", "amount": 10}
[OrbitStripe] ← RPC Response: orbit_stripe_refund_payment {"success": true, "refund_id": "re_3TF...", "amount": 10}
[OrbitStripe] ━━━ REFUND COMPLETE ━━━
[OrbitStripe] Refund ID: re_3TFxxxxxx | Amount: £10
```

---

## Payment Status Flow

```
Draft
  ↓ Create Intent
Intent Created
  ↓ Collect Payment
Processing
  ↓ Capture
Succeeded ←──────────────────────┐
  ↓ Issue Refund (partial)       │ Webhook: charge.refunded
Partially Refunded               │
  ↓ Issue remaining refund       │
Refunded ←───────────────────────┘

Failed (terminal error / card declined)
Cancelled (cashier cancelled before capture)
```

---

## Troubleshooting Refunds

### `Refunds can only be issued for succeeded payments`

The payment must be in **Succeeded** or **Partially Refunded** state.

- Check the payment status in Stripe Terminal Payments list
- If status is wrong, check Stripe Dashboard for actual payment status

### `Refund amount cannot exceed maximum refundable amount`

You're trying to refund more than was paid (or more than remains after partial refunds.

- Check the **Refunded Amount** field on the payment record
- Maximum = Original Amount - Already Refunded

### `Cannot refund: no Stripe PaymentIntent ID`

The POS refund line doesn't have the original transaction ID.

- This happens if the original payment was not made through Stripe Terminal
- Use **Method 3 (Stripe Dashboard)** to refund manually

### Refund not appearing on customer's statement

- Refunds take 5–10 business days — this is normal
- Verify in Stripe Dashboard → Payments → the charge → Refunds tab
- If the refund shows in Stripe but not in customer's account, contact their bank

### Odoo status not updating after Stripe Dashboard refund

- Set up the `charge.refunded` webhook event
- Without it, Odoo won't know about refunds made outside Odoo
- Manually update the record: open payment → edit State to **Refunded**
