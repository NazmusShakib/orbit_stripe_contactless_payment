# Stripe Terminal — Webhook & Simulation Guide

How to see every request/response in dev mode and how to test webhooks locally.

---

## Part 1 — Watching Requests in Real-Time (Dev Mode)

### Browser Console (Most Important)

Every step of the payment flow is logged to the browser console with `[OrbitStripe]` prefix.

**How to open:**

- Chrome/Edge: `F12` → **Console** tab
- Firefox: `F12` → **Console** tab
- Safari: `Cmd+Option+I` → **Console** tab

**Filter to see only Stripe logs:**
Type `[OrbitStripe]` in the console filter box.

**What you will see during a payment:**

```
[OrbitStripe] ━━━ PAYMENT FLOW START ━━━
[OrbitStripe] Amount: 10 | testMode: true

▶ [OrbitStripe] Step 1: Create PaymentIntent (server → Stripe API)
  [OrbitStripe] → RPC Request: orbit_stripe_payment_intent {"amount": 10}
  [OrbitStripe] ← RPC Response: orbit_stripe_payment_intent {
    "id": "pi_3TF...",
    "status": "requires_payment_method",
    "amount": 1000,
    "currency": "gbp"
  }

▶ [OrbitStripe] Step 2: collectPaymentMethod (Stripe Terminal SDK → Reader)
  [OrbitStripe] Calling terminal.collectPaymentMethod with client_secret...
  [OrbitStripe] [TEST MODE] Card tap will be simulated automatically by Stripe SDK
  [OrbitStripe] collectPaymentMethod SUCCESS. PaymentIntent status: requires_capture

▶ [OrbitStripe] Step 3: processPayment (Stripe Terminal SDK → Stripe API)
  [OrbitStripe] processPayment SUCCESS. Status: requires_capture

▶ [OrbitStripe] Step 4: Capture (server → Stripe API)
  [OrbitStripe] Step 4: Capturing PaymentIntent pi_3TF...
  [OrbitStripe] Capture SUCCESS. Status: succeeded | latest_charge: ch_3TF...
  [OrbitStripe] Card brand: visa | last4: 4242 | funding: credit | country: US

[OrbitStripe] ━━━ PAYMENT FLOW COMPLETE ━━━
[OrbitStripe] transaction_id: pi_3TF...
[OrbitStripe] card_type: visa
```

### Odoo Server Logs (Python side)

Every Stripe API call on the server is also logged. View in real-time:

```bash
# Docker — follow logs live
docker logs odoo16_app -f 2>&1 | grep -E "(OrbitStripe|stripe|Stripe|orbit)"

# Or tail the log file
docker exec odoo16_app tail -f /app/odoo-server/log/odoo/odoo.log | grep -i stripe
```

**What you see server-side:**

```
INFO orbit_stripe_contactless_payment.models.pos_payment_method: POS PaymentIntent: method=Card amount=10.0 gbp (1000 units)
INFO stripe_terminal_service: Creating PaymentIntent: amount=1000 gbp, types=['card_present'], capture=manual
INFO stripe_terminal_service: PaymentIntent created: pi_3TF... (status=requires_payment_method)
INFO orbit_stripe_contactless_payment.models.pos_payment_method: Capturing POS PaymentIntent: pi_3TF... (amount_int=None)
INFO stripe_terminal_service: Capturing PaymentIntent: pi_3TF... (amount=None)
INFO orbit_stripe_contactless_payment.models.pos_payment_method: Captured. Charge: ch_3TF... | brand: visa | last4: 4242 | funding: credit
INFO orbit_stripe_contactless_payment.models.pos_payment_method: POS PaymentIntent pi_3TF... captured successfully. Status: succeeded
```

### Stripe Dashboard (Test Mode)

See every API call Stripe received from your Odoo server:

1. Go to https://dashboard.stripe.com/test
2. Click **Developers → Logs**
3. Filter by: `POST /v1/payment_intents` or `POST /v1/terminal`
4. Click any log entry to see full request + response JSON

---

## Part 2 — Stripe CLI for Local Webhook Testing

The Stripe CLI lets you forward real Stripe webhook events to your local Odoo (no HTTPS needed).

### Install Stripe CLI

```bash
# Mac (Homebrew)
brew install stripe/stripe-cli/stripe

# Linux
curl -s https://packages.stripe.dev/api/security/keypair/stripe-cli-gpg/public | gpg --dearmor | sudo tee /usr/share/keyrings/stripe.gpg
echo "deb [signed-by=/usr/share/keyrings/stripe.gpg] https://packages.stripe.dev/stripe-cli-debian-stretch stable main" | sudo tee -a /etc/apt/sources.list.d/stripe.list
sudo apt update && sudo apt install stripe

# Windows
scoop install stripe
# OR download from: https://github.com/stripe/stripe-cli/releases
```

### Login to Stripe CLI

```bash
stripe login
```

Opens a browser — authorise with your Stripe account.

### Forward Webhooks to Local Odoo

```bash
# Replace 8069 with your Odoo port
stripe listen --forward-to http://localhost:8069/stripe/terminal/webhook
```

You will see:

```
> Ready! You are using Stripe API Version [2024-xx-xx]. Your webhook signing secret is whsec_test_xxxxx...
```

**Copy the `whsec_test_...` secret** and paste it into:
**Odoo → Settings → Stripe Terminal → Webhook Secret**

### Trigger Test Events

In a second terminal, trigger events manually:

```bash
# Simulate a successful payment
stripe trigger payment_intent.succeeded

# Simulate a payment failure
stripe trigger payment_intent.payment_failed

# Simulate a cancellation
stripe trigger payment_intent.canceled
```

Or trigger with a specific PaymentIntent ID:

```bash
stripe trigger payment_intent.succeeded \
  --override payment_intent:id=pi_3TFrrYK4sPO78s171DpqJfER
```

### Watch events in real-time

```bash
# Stream all events (no forwarding)
stripe events resend pi_3TFxxxx_secret --live
```

---

## Part 3 — Full Simulation Flow (Step by Step)

Here is exactly what happens when you take a payment in test mode:

```
Browser (POS JS)                    Odoo Server (Python)             Stripe API
─────────────────                   ────────────────────             ──────────
[1] Send payment clicked
    → RPC: orbit_stripe_payment_intent(amount=10.0)
                                    → stripe.payment_intents.create({
                                        amount: 1000,           ──────────────→
                                        currency: 'gbp',                       Stripe creates PI
                                        payment_method_types: ['card_present'], ←────────────────
                                        capture_method: 'manual'               {id: 'pi_3TF...'}
                                      })
    ← {id: 'pi_3TF...', client_secret: 'pi_3TF..._secret...'}

[2] terminal.collectPaymentMethod(client_secret)
    Stripe Terminal SDK connects to simulated reader
    [TEST MODE: SDK auto-simulates card tap]
    ← {paymentIntent: {status: 'requires_capture'}}

[3] terminal.processPayment(paymentIntent)
    Stripe Terminal SDK sends cryptographic confirmation ──────────→
                                                                    Stripe confirms payment
                                                        ←────────── {status: 'requires_capture'}
    ← {paymentIntent: {status: 'requires_capture'}}

[4] RPC: orbit_stripe_capture_payment(pi_id)
                                    → stripe.payment_intents.capture(pi_id) ──→
                                                                    Stripe captures funds
                                    ← {status: 'succeeded',        ←──────────
                                        latest_charge: 'ch_3TF...'}
                                    → stripe.charges.retrieve(ch_id) ─────────→
                                                                    Returns card details
                                    ← {brand: 'visa', last4: '4242'} ←────────

[5] POS shows Payment done
    Webhook (if configured):
    Stripe ──────────────────────────────────────────→ /stripe/terminal/webhook
                                    payment_intent.succeeded event received
                                    Odoo updates StripeTerminalPayment record
```

---

## Part 4 — Test Cards (Simulated Reader)

Stripe's simulated reader always uses the following test card details:

| Field   | Value           |
| ------- | --------------- |
| Brand   | Visa            |
| Last4   | 4242            |
| Expiry  | 12/34           |
| Funding | Credit          |
| Country | US              |
| CVC     | 100             |
| Status  | Always succeeds |

To test **declined payments** in simulation, use Stripe's test payment amounts:

- `£0.02` → Card declined
- `£0.91` → Insufficient funds
- `£0.05` → Expired card

Or trigger declines via Stripe CLI:

```bash
stripe trigger payment_intent.payment_failed
```

---

## Part 5 — Debugging Common Issues

### Check if webhook is receiving events

```bash
# While stripe listen is running, make a payment in POS
# You should see in CLI terminal:
# 2024-xx-xx --> payment_intent.succeeded [evt_xxx]
# 2024-xx-xx <-- [200] POST http://localhost:8069/stripe/terminal/webhook [evt_xxx]
```

### Check Odoo received the webhook

```bash
docker logs odoo16_app 2>&1 | grep -i webhook
# Should show: "Stripe webhook: type=payment_intent.succeeded id=evt_xxx"
```

### Check PaymentIntent in Stripe Dashboard

1. https://dashboard.stripe.com/test/payments
2. Find your payment by amount/date
3. Click it to see full timeline: created → processing → captured → succeeded

### Network tab (Browser DevTools)

1. `F12` → **Network** tab
2. Filter by `call_kw` or `orbit_stripe`
3. Click any request to see the full JSON body and response
4. Look for `orbit_stripe_payment_intent`, `orbit_stripe_capture_payment` etc.

---

## Part 6 — Enable Odoo Debug Mode

Odoo debug mode gives extra developer info in the UI:

1. Go to `http://localhost:8069/web?debug=1` (add `?debug=1` to URL)
2. Or: Settings → Activate Developer Mode
3. In POS: add `?debug=1` to the POS URL

In debug mode you can see:

- Technical menu items
- Field names on forms
- View IDs
- Full error tracebacks

---

## Quick Reference

| What to check      | Where to look                                                                   |
| ------------------ | ------------------------------------------------------------------------------- |
| Browser JS logs    | F12 → Console → filter `[OrbitStripe]`                                          |
| Server Python logs | `docker logs odoo16_app -f \| grep stripe`                                      |
| Stripe API calls   | dashboard.stripe.com/test → Developers → Logs                                   |
| Stripe events      | dashboard.stripe.com/test → Developers → Events                                 |
| Webhook delivery   | Stripe CLI: `stripe listen --forward-to localhost:8069/stripe/terminal/webhook` |
| Payment details    | dashboard.stripe.com/test/payments                                              |
| Reader status      | dashboard.stripe.com/test/terminal/readers                                      |
