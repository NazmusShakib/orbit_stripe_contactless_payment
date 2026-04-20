# Stripe Terminal — Webhook and Simulation Guide

This guide covers the current webhook behavior and local Stripe CLI testing flow.

---

## 1. What Webhooks Are Used For

This module can process Stripe webhooks at:

```text
/stripe/terminal/webhook
```

Current webhook handling covers:

- `payment_intent.succeeded`
- `payment_intent.payment_failed`
- `payment_intent.canceled`
- `charge.refunded`
- `terminal.reader.action_failed`

Webhooks are especially useful for:

- dashboard-origin refunds
- backend state synchronization
- refund confirmation outside the normal Odoo user flow

---

## 2. Signature Verification

If `Webhook Secret` is configured in:

- `Settings -> Stripe Terminal`

the module verifies Stripe webhook signatures.

If no secret is configured:

- the payload is still accepted
- but it is processed without verification
- this is not recommended for production

---

## 3. Stripe CLI Local Setup

### Start forwarding

```bash
stripe listen --forward-to http://YOUR_LOCAL_ODOO_HOST:8069/stripe/terminal/webhook
```

Replace `YOUR_LOCAL_ODOO_HOST` and port `8069` if your local Odoo runs somewhere else.

You will see a generated:

```text
whsec_...
```

Copy that secret into:

- `Settings -> Stripe Terminal -> Webhook Secret`

Then click `Save`.

---

## 4. Useful Test Events

You can trigger events like:

```bash
stripe trigger payment_intent.succeeded
stripe trigger payment_intent.payment_failed
stripe trigger payment_intent.canceled
stripe trigger charge.refunded
```

For local webhook testing, `charge.refunded` is the most useful one when verifying dashboard refund sync.

---

## 5. How To Watch Delivery

### Stripe CLI terminal

When forwarding is running, you should see:

- webhook sent
- webhook delivered
- HTTP response status

### Odoo logs

```bash
docker compose logs -f YOUR_ODOO_SERVICE
```

Look for lines containing:

- `Stripe webhook`
- `charge.refunded`
- `payment_intent`

### Stripe Dashboard

Check:

- `Developers -> Events`
- `Developers -> Webhooks`

---

## 6. What Should Update in Odoo

### Payment events

When the matching backend record exists, webhook processing can update:

- payment state
- error message
- chatter log

### Refund events

For `charge.refunded`, Odoo can update:

- `Stripe Refund ID`
- `Refunded Amount`
- `Refund Reason`
- `Refund Date`
- payment state to `Partially Refunded` or `Refunded`

---

## 7. Recommended Production Webhook Setup

In Stripe Dashboard, create a webhook endpoint with:

```text
https://YOUR-DOMAIN/stripe/terminal/webhook
```

Recommended events:

- `payment_intent.succeeded`
- `payment_intent.payment_failed`
- `payment_intent.canceled`
- `charge.refunded`
- `terminal.reader.action_failed`

Then:

1. copy the production `whsec_...`
2. save it in Odoo Settings
3. test one payment and one refund

---

## 8. Current Simulation Notes

In test mode:

- backend payment flow can use simulated Stripe readers
- POS payment flow can also use simulated readers
- refund webhook simulation is best tested with Stripe CLI forwarding

For refund testing, pair this guide with:

- [REFUND_TEST_GUIDE.md](REFUND_TEST_GUIDE.md)

---

## 9. Common Issues

### Webhook delivered but Odoo did not update

Check:

- the Stripe event actually matches an Odoo payment record
- the correct webhook secret is configured
- Odoo logs for processing errors

### Unauthorized / signature verification failure

Cause:

- wrong `whsec_...`

Fix:

- copy the current secret again from Stripe or Stripe CLI

### Dashboard refund not reflected in Odoo

Cause:

- `charge.refunded` was not configured or not delivered

Fix:

- add `charge.refunded`
- verify delivery
- verify the Odoo record can be found by PaymentIntent ID or charge ID

---

## 10. Quick Command Reference

### Start local forwarding

```bash
stripe listen --forward-to http://YOUR_LOCAL_ODOO_HOST:8069/stripe/terminal/webhook
```

### Tail Odoo logs

```bash
docker compose logs -f YOUR_ODOO_SERVICE
```

### Open Odoo in debug mode

```text
http://YOUR_LOCAL_ODOO_HOST:8069/web?debug=1
```

---

## 11. Related Guides

- [REFUND_TEST_GUIDE.md](REFUND_TEST_GUIDE.md)
- [REFUND_POLICY.md](REFUND_POLICY.md)
- [DEBUG_AND_FAQ.md](DEBUG_AND_FAQ.md)
- [README_LIVE_MODE.md](README_LIVE_MODE.md)
