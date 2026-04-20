# Stripe Terminal — Debug and FAQ

Use this guide for the current module behavior.

Command examples below use placeholders:

- `YOUR_ODOO_SERVICE` = service that runs Odoo
- `YOUR_DB_SERVICE` = service that runs PostgreSQL
- `YOUR_DB_NAME` = Odoo database name
- `YOUR_ODOO_SRC` = path inside container that contains `odoo-bin`
- `YOUR_ODOO_CONF` = Odoo config file path or filename

---

## 1. Where To Look First

### Backend payment records

Open:

- `Stripe Terminal -> Payments -> All Payments`

This is the fastest place to check:

- source (`Backend` or `POS`)
- payment state
- Stripe PaymentIntent ID
- Stripe charge ID
- refund fields
- POS linkage
- chatter history

### Odoo logs

```bash
docker compose logs -f YOUR_ODOO_SERVICE
```

### Browser console

In POS, filter the console by:

```text
[OrbitStripe]
```

### Stripe Dashboard

Check:

- `Payments`
- `Developers -> Logs`
- `Developers -> Events`

---

## 2. Most Common Payment Issues

### Payment still behaves like test mode

Cause:

- settings were changed while POS was already open

Fix:

1. save settings
2. close the POS tab
3. reopen the POS session

### Same-network reader error in POS

Cause:

- no configured `reader_id` was available, so POS fell back to browser SDK discovery

Fix:

- set a global Stripe reader in `Settings -> Stripe Terminal`
- or set a payment-method override reader on the POS payment method

When a configured reader exists, Odoo prefers the server-side reader path.

### Reader not found

Cause:

- wrong `tmr_...`
- wrong test/live account

Fix:

- copy the reader ID again from Stripe Dashboard for the correct mode

### Reader stays on tap screen after cancel

Current implementation should clear the active reader action when cancelling.

If it does not:

- refresh the POS/browser
- retry once
- check `docker compose logs -f YOUR_ODOO_SERVICE` for reader cancel errors

### Payment succeeded in Stripe but backend record looks stale

Check:

- whether the normal capture flow completed
- whether webhook sync is configured
- whether you are looking at the correct payment record

---

## 3. Most Common Refund Issues

### Cashier tried to refund from the POS payment line

Current module behavior:

- Stripe Terminal refunds should be run from the backend `Stripe Terminal Payments` flow

Use:

- open the backend payment record
- click `Issue Refund`

### POS-linked refund says a session is required

Cause:

- POS-linked refunds create a real Odoo POS refund order/payment
- that requires an open session on the same POS config

Fix:

- open the related POS session
- retry the backend refund

### Selected POS refund amount is too high

Cause:

- selected lines/quantities exceed remaining Stripe refundable amount

Fix:

- reduce selected quantities

### Dashboard refund did not update Odoo

Cause:

- webhook not configured
- `charge.refunded` not delivered

Fix:

- configure webhook forwarding / production webhook
- set `Webhook Secret`
- include `charge.refunded`

---

## 4. Receipt / Printer Questions

### Why does Receipt not download a PDF now?

Current behavior:

- `Receipt` and `Refund` open thermal HTML pages
- printing is handled by the browser

See:

- [PRINTER_SETUP_GUIDE.md](PRINTER_SETUP_GUIDE.md)

### Why does it still print like a full page?

Usually this is printer or browser setup, not the Odoo template.

Check:

- paper size `80mm` or `58mm`
- margins `None`
- headers / footers off
- scale `100%`

---

## 5. Webhook Questions

### Where is the webhook endpoint?

```text
/stripe/terminal/webhook
```

### Which events matter most?

- `payment_intent.succeeded`
- `payment_intent.payment_failed`
- `payment_intent.canceled`
- `charge.refunded`
- `terminal.reader.action_failed`

### How do I test it locally?

```bash
stripe listen --forward-to http://YOUR_LOCAL_ODOO_HOST:8069/stripe/terminal/webhook
```

Then copy the generated `whsec_...` into Odoo settings.

See:

- [WEBHOOK_SIMULATION_GUIDE.md](WEBHOOK_SIMULATION_GUIDE.md)

---

## 6. Useful Commands

### Upgrade the module

```bash
docker compose exec YOUR_ODOO_SERVICE bash -lc 'cd YOUR_ODOO_SRC && python3 odoo-bin -c YOUR_ODOO_CONF -d YOUR_DB_NAME -u orbit_stripe_contactless_payment --stop-after-init'
```

### Start Odoo

```bash
docker compose exec -d YOUR_ODOO_SERVICE bash -lc 'cd YOUR_ODOO_SRC && nohup python3 odoo-bin --config=YOUR_ODOO_CONF >/tmp/odoo.log 2>&1 &'
```

### Odoo shell

```bash
docker compose exec YOUR_ODOO_SERVICE bash -lc 'cd YOUR_ODOO_SRC && python3 odoo-bin shell -c YOUR_ODOO_CONF -d YOUR_DB_NAME --no-http'
```

### PostgreSQL shell

```bash
docker compose exec YOUR_DB_SERVICE psql -U YOUR_DB_USER -d YOUR_DB_NAME
```

---

## 7. Quick Diagnostic Checklist

### Payment issue

- is Odoo running?
- are the correct Stripe keys configured?
- is `Test Mode` correct?
- is the correct `reader_id` configured?
- was POS reopened after changing settings?
- does the Stripe payment record show an error message?
- do Odoo logs show Stripe or reader errors?

### Refund issue

- is the payment state `Succeeded` or `Partially Refunded`?
- for POS-linked refunds, is the related POS session open?
- is the selected refund amount valid?
- if refunded in Stripe Dashboard, is `charge.refunded` configured?

### Printer issue

- does the print open as HTML?
- is the correct thermal printer selected?
- is paper size correct?

---

## 8. Related Guides

- [INSTALLATION_GUIDE.md](INSTALLATION_GUIDE.md)
- [README_LIVE_MODE.md](README_LIVE_MODE.md)
- [REFUND_POLICY.md](REFUND_POLICY.md)
- [REFUND_TEST_GUIDE.md](REFUND_TEST_GUIDE.md)
- [PRINTER_SETUP_GUIDE.md](PRINTER_SETUP_GUIDE.md)
- [WEBHOOK_SIMULATION_GUIDE.md](WEBHOOK_SIMULATION_GUIDE.md)
