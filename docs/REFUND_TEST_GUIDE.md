# Stripe Terminal — Refund Test Guide

Use this guide to test the current refund flow safely in Stripe test mode.

This guide matches the current implementation:

- Stripe Terminal refunds are initiated from the backend `Stripe Terminal Payments` flow
- POS-linked refunds create real Odoo POS refund orders/payments before refunding in Stripe

---

## 1. Prerequisites

Before testing refunds, make sure:

- test keys are configured
- a simulated Stripe reader exists
- the module is installed and upgraded
- the Odoo server is running

For POS-linked refund tests:

- the original POS payment must have been made through `Stripe Terminal (Orbit)`
- the same POS configuration must have an open session at refund time

---

## 2. Test A — Backend-Origin Payment and Refund

### Create the payment

1. Go to `Stripe Terminal -> Payments -> New Payment`
2. Enter a small test amount
3. Click `1. Create Payment Intent`
4. Click `2. Simulate Card Tap`
5. Click `3. Check / Capture Payment`
6. Confirm the payment reaches `Succeeded`

### Refund the payment

1. On the same payment, click `Issue Refund`
2. Choose full or partial refund
3. Confirm

Expected result:

- status becomes `Partially Refunded` or `Refunded`
- `Stripe Refund ID` is stored
- `Refunded Amount` updates
- `Refund` print button becomes available

---

## 3. Test B — POS Payment Then Backend Refund

### Take the POS payment

1. Open the POS session
2. Add a product
3. Go to payment
4. Use the Stripe Terminal payment method
5. Complete the payment

Expected result:

- the POS order is paid
- a backend `Stripe Terminal Payments` record is created with `Source = POS`

### Refund it from the backend

1. Keep or reopen an open session on the same POS config
2. Open the related payment in `Stripe Terminal -> Payments -> All Payments`
3. Click `Issue Refund`
4. Select refund quantities on the order lines
5. Confirm

Expected result:

- Stripe refund succeeds
- an Odoo POS refund order is created
- an Odoo refund payment is created
- the Stripe payment record links the POS refund order/payment
- `Refund` print button becomes available

---

## 4. Test C — Stripe Dashboard Refund Sync

This test verifies webhook-based synchronization.

### Set up webhook forwarding locally

Run:

```bash
stripe listen --forward-to http://YOUR_LOCAL_ODOO_HOST:8069/stripe/terminal/webhook
```

Replace `YOUR_LOCAL_ODOO_HOST` and port `8069` if your local Odoo runs on a different host or port.

Copy the reported `whsec_...` secret into:

- `Settings -> Stripe Terminal -> Webhook Secret`

### Refund from Stripe Dashboard

1. Open the Stripe test dashboard payment
2. Refund it directly in Stripe
3. Watch the CLI output
4. Check Odoo

Expected result:

- Stripe CLI shows the webhook delivered
- Odoo backend record updates automatically
- refund fields and status are synchronized

---

## 5. Optional Log Checks

### Browser console during POS payment

Filter:

```text
[OrbitStripe]
```

### Odoo app logs

```bash
docker compose logs -f YOUR_ODOO_SERVICE
```

### Stripe Dashboard

Check:

- `Payments`
- `Developers -> Logs`
- `Developers -> Events`

---

## 6. Current Expected Behavior

### Supported

- backend-origin refund from backend payment record
- POS-linked refund from backend payment record
- webhook sync for dashboard refunds

### Not the supported Stripe refund path

- refunding the Stripe Terminal payment directly from the POS payment line UI

Use the backend `Stripe Terminal Payments` refund flow instead.

---

## 7. Common Test Failures

### No open POS session

For POS-linked refunds, open a session on the same POS config and retry.

### Selected POS refund exceeds remaining Stripe amount

Reduce the selected quantities or remaining amount.

### Dashboard refund not synced to Odoo

Configure:

- `charge.refunded`
- correct `whsec_...`
- webhook forwarding

---

## 8. Minimal Test Checklist

- backend test payment succeeds
- backend refund succeeds
- POS payment succeeds
- POS-linked backend refund succeeds
- refund receipt prints
- webhook dashboard refund sync works

---

## 9. Related Guides

- [REFUND_POLICY.md](REFUND_POLICY.md)
- [WEBHOOK_SIMULATION_GUIDE.md](WEBHOOK_SIMULATION_GUIDE.md)
- [PRINTER_SETUP_GUIDE.md](PRINTER_SETUP_GUIDE.md)
- [DEBUG_AND_FAQ.md](DEBUG_AND_FAQ.md)
