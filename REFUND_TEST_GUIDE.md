# Stripe Terminal — Refund Test Guide (Simulation Mode)

Follow this guide step-by-step to test the full payment + refund flow yourself.
No real money involved — everything uses Stripe test keys.

---

## What We Verified (Auto-tested)

The following was tested and confirmed working on your system:

```
Step 1:  Create PaymentIntent £15.00 GBP           >  pi_3TFsAj...
Step 2:  Instruct simulated reader                 >  tmr_GcRIdgNLiwdmno
Step 3:  Simulate card tap (Visa 4242)             >  action: succeeded
Step 4:  Check PI status → requires_capture        >
Step 5:  Capture payment                           >  status: succeeded
Step 5b: Card details: Visa 4242 credit (US)       >
Step 6:  Partial refund £5.00                      >  re_3TFsAj... succeeded
Step 7:  Partial refund £3.00                      >  re_3TFsAj... succeeded
Step 8:  Final refund £7.00                        >  re_3TFsAj... succeeded
Step 9:  Charge fully refunded £15.00/£15.00       >  refunded=True
Step 10: All 3 refunds listed on PaymentIntent     >  total=£15.00
```

---

## Part A — Test Refund via POS (Browser)

### Prerequisites

- Module installed and Odoo running
- POS payment method "Card / Contactless" set up with Stripe Terminal (Orbit)
- Company currency = GBP

---

### Step 1 — Open POS and Take a Payment

1. Go to **Point of Sale → Dashboard**
2. Click **Open** on your POS session (or start a new session)
3. Add any product to the order (e.g. quantity 1 × £10.00)
4. Click **Payment**
5. Click **Card / Contactless**
6. Click **Send** (or Validate)

**Watch in browser console (F12 → Console, filter `[OrbitStripe]`):**

```
[OrbitStripe] ━━━ PAYMENT FLOW START ━━━
[OrbitStripe] Step 1: Create PaymentIntent (server → Stripe API)
[OrbitStripe] → RPC Request: orbit_stripe_payment_intent {"amount": 10}
[OrbitStripe] ← RPC Response: {"id": "pi_3T...", "status": "requires_payment_method", "amount": 1000, "currency": "gbp"}
[OrbitStripe] Step 2: collectPaymentMethod (Stripe Terminal SDK → Reader)
[OrbitStripe] [TEST MODE] Card tap will be simulated automatically by Stripe SDK
[OrbitStripe] collectPaymentMethod SUCCESS. PaymentIntent status: requires_capture
[OrbitStripe] Step 3: processPayment (Stripe Terminal SDK → Stripe API)
[OrbitStripe] processPayment SUCCESS. Status: requires_capture
[OrbitStripe] Step 4: Capture (server → Stripe API)
[OrbitStripe] Capture SUCCESS. Status: succeeded | latest_charge: ch_3T...
[OrbitStripe] Card brand: visa | last4: 4242 | funding: credit
[OrbitStripe] ━━━ PAYMENT FLOW COMPLETE ━━━
```

7. POS shows **Payment Done**
8. Click **New Order** to close the payment screen

---

### Step 2 — Verify Payment in Stripe Dashboard

1. Open https://dashboard.stripe.com/test/payments
2. You should see your payment: **£10.00 — Succeeded**
3. Click it to see full details:
   - Status: **Succeeded**
   - Payment method: Visa ···· 4242
   - Refunds: none yet

---

### Step 3 — Issue Refund via POS

1. In POS, click the **Orders** icon (clock/history icon, top right)
2. Find your order → click it to open
3. Click **Return** button
4. Select all items (or choose which ones to return)
5. Click **Return** to confirm
6. A new **negative-amount order** opens (e.g. -£10.00)
7. Click **Payment**
8. The refund amount is pre-filled (£10.00)
9. Click **Validate**

**Watch in browser console:**

```
[OrbitStripe] ━━━ REFUND FLOW START ━━━
[OrbitStripe] transaction_id (PaymentIntent): pi_3T...
[OrbitStripe] Refund amount: 10
[OrbitStripe] → RPC Request: orbit_stripe_refund_payment {"payment_intent_id": "pi_3T...", "amount": 10}
[OrbitStripe] ← RPC Response: {"success": true, "refund_id": "re_3T...", "amount": 10, "status": "succeeded"}
[OrbitStripe] ━━━ REFUND COMPLETE ━━━
[OrbitStripe] Refund ID: re_3T... | Amount: £10
```

10. POS shows **Reversed**

---

### Step 4 — Verify Refund in Stripe Dashboard

1. Go back to https://dashboard.stripe.com/test/payments
2. Find your payment — it now shows **Refunded**
3. Click it → under **Refunds** you'll see:
   - `re_3T...` | £10.00 | succeeded | requested_by_customer

---

## Part B — Test Refund via Odoo Backend

### Step 1 — Take a backend payment

1. Go to **Point of Sale → Stripe Terminal Payments** (or **Orbit → Stripe Terminal**)
2. Click **New**
3. Fill in:
   - **Amount**: `20.00`
   - **Currency**: GBP
   - **Description**: `Backend refund test`
4. Click **Save**
5. Click **Create Payment Intent**
6. Click **Simulate Payment** (test mode)
7. Click **Confirm Payment**
8. Status changes to **Succeeded**

---

### Step 2 — Issue partial refund from backend

1. On the succeeded payment record, click **Issue Refund**
2. A dialog opens:
   - **Refund Type**: Select **Partial Refund**
   - **Amount to Refund**: Enter `8.00`
   - **Reason**: Requested by Customer
   - **Internal Note**: `Customer returned half the order`
3. Click **Issue Refund** (red button)
4. Status changes to **Partially Refunded**
5. Chatter shows: `PARTIAL REFUND issued: £8.00 | Stripe Refund ID: re_3T...`

---

### Step 3 — Issue remaining refund

1. Click **Issue Refund** again
2. **Refund Type**: Full Refund
3. **Amount**: pre-filled as £12.00 (remaining)
4. Click **Issue Refund**
5. Status changes to **Refunded**
6. Chatter shows: `FULL REFUND issued: £12.00`

---

## Part C — Test via Stripe CLI (Webhook Simulation)

This lets you simulate what happens when a refund is issued from the Stripe Dashboard.

### Step 1 — Install Stripe CLI

```bash
# Mac
brew install stripe/stripe-cli/stripe

# Linux
curl -s https://packages.stripe.dev/api/security/keypair/stripe-cli-gpg/public | \
  gpg --dearmor | sudo tee /usr/share/keyrings/stripe.gpg
echo "deb [signed-by=/usr/share/keyrings/stripe.gpg] \
  https://packages.stripe.dev/stripe-cli-debian-stretch stable main" | \
  sudo tee -a /etc/apt/sources.list.d/stripe.list
sudo apt update && sudo apt install stripe

# Windows: download from https://github.com/stripe/stripe-cli/releases
```

### Step 2 — Login

```bash
stripe login
# Opens browser — authorise with your Stripe account
```

### Step 3 — Start webhook forwarding

Open a terminal and run:

```bash
stripe listen --forward-to http://localhost:8069/stripe/terminal/webhook
```

You'll see:

```
> Ready! Your webhook signing secret is whsec_test_xxxxxxxxx
```

**Copy that `whsec_test_...` secret** and go to:
**Odoo → Settings → Stripe Terminal → Webhook Secret** → paste it → Save

### Step 4 — Take a payment (get a real PaymentIntent ID)

Either:

- Take a payment via POS (note the `pi_...` from browser console)
- Or take one via backend (see Part B Step 1)
- Or check the Stripe Dashboard for any recent `pi_...`

### Step 5 — Trigger a refund webhook

In a second terminal:

```bash
# Replace with a real PaymentIntent ID from your system
stripe trigger charge.refunded
```

In the first terminal (stripe listen), you'll see:

```
--> charge.refunded [evt_3T...]
<-- [200] POST http://localhost:8069/stripe/terminal/webhook [evt_3T...]
```

In Odoo logs:

```bash
docker logs odoo16_app -f 2>&1 | grep -i refund
# Should show: "Webhook: charge.refunded for payment STP/... £x.xx (FULL)"
```

### Step 6 — Check Odoo updated automatically

1. Go to **Stripe Terminal Payments**
2. Find the payment → status should be **Refunded**
3. Chatter shows: `💸 Refund confirmed via Stripe webhook.`

---

## Part D — Test via Direct API (Python Script)

You can run this test yourself on your server at any time:

```bash
docker exec odoo16_app python3 - << 'EOF'
import stripe

SECRET = 'sk_test_************************'
READER = 'tmr_GcRIdgNLiwdmno'
client = stripe.StripeClient(SECRET)

def d(obj):
    if hasattr(obj, '_data'): return {k: d(v) for k, v in obj._data.items()}
    if isinstance(obj, dict): return {k: d(v) for k, v in obj.items()}
    if isinstance(obj, list): return [d(i) for i in obj]
    return obj

# 1. Create PI
pi = d(client.v1.payment_intents.create({
    'amount': 1000, 'currency': 'gbp',
    'payment_method_types': ['card_present'], 'capture_method': 'manual',
}))
print('PI:', pi['id'])

# 2. Instruct reader
client.v1.terminal.readers.process_payment_intent(READER, {'payment_intent': pi['id']})
client.v1.test_helpers.terminal.readers.present_payment_method(READER)

# 3. Capture
cap = d(client.v1.payment_intents.capture(pi['id'], {}))
print('Captured:', cap['status'], '| charge:', cap['latest_charge'])

# 4. Refund
ref = d(client.v1.refunds.create({'payment_intent': pi['id'], 'reason': 'requested_by_customer'}))
print('Refund:', ref['id'], '| status:', ref['status'], '| amount: £', ref['amount']/100)
print(' Done!')
EOF
```

Expected output:

```
PI: pi_3T...
Captured: succeeded | charge: ch_3T...
Refund: re_3T... | status: succeeded | amount: £ 10.0
Done!
```

---

## Part E — Verify in Stripe Dashboard

After any test, verify at https://dashboard.stripe.com/test/payments:

| Column        | Expected  |
| ------------- | --------- |
| Status        | Refunded  |
| Amount        | £X.XX     |
| Refunds       | re\_...   |
| Refund status | Succeeded |

Click any payment → **Refunds** tab shows all refunds with amounts and timestamps.

---

## What the Simulated Card Always Returns

In test/simulation mode, Stripe always uses this test card:

| Field   | Value  |
| ------- | ------ |
| Brand   | Visa   |
| Last 4  | 4242   |
| Expiry  | 12/34  |
| Funding | Credit |
| Country | US     |

To simulate a **declined payment** (for testing error handling), use these amounts:

- `£0.02` → Card declined (generic)
- `£0.91` → Insufficient funds
- `£0.05` → Expired card
- `£0.04` → Lost card

---

## Troubleshooting

### Refund fails with "charge not found"

The PaymentIntent ID on the payment line may be wrong. Check:

- Browser console: `[OrbitStripe] transaction_id:` value during the original payment
- Stripe Dashboard → find the payment by amount/date

### POS refund shows "No Transaction ID"

The original payment wasn't made through Stripe Terminal (no `pi_...` stored).
Use **Backend refund (Part B)** or **Stripe Dashboard (Part D step 5)**.

### Stripe Dashboard refund doesn't update Odoo

Set up webhook forwarding (Part C) and add `charge.refunded` to your webhook events.

### `Refund amount cannot exceed maximum`

You're trying to refund more than was paid. Check the **Refunded Amount** field on the record.

---

## Console Log Reference

| Log                                          | Meaning                                          |
| -------------------------------------------- | ------------------------------------------------ |
| `━━━ REFUND FLOW START ━━━`                  | Cashier clicked Validate on refund order         |
| `→ RPC Request: orbit_stripe_refund_payment` | Calling server to process refund                 |
| `← RPC Response: {"success": true}`          | Stripe accepted the refund                       |
| `━━━ REFUND COMPLETE ━━━`                    | Refund processed successfully                    |
| `Refund FAILED: ...`                         | Stripe rejected — see error message              |
| `No Transaction ID`                          | Original payment not linked — use backend refund |
