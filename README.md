# Stripe Terminal Payment — Odoo Module

> Supports both **test** and **live** Stripe Terminal payments in Odoo, including backend and POS payment flows.

---

## Module Overview

This module integrates **Stripe Terminal** into Odoo 16 for in-person card payments.

It currently supports:

- Backend `Stripe Terminal Payments` records for manual payment flow
- POS card/contactless payments through `Stripe Terminal (Orbit)`
- Test mode with simulated Stripe readers
- Live mode with registered Stripe Terminal readers
- Global reader configuration in Settings with optional per-payment-method override
- POS payment audit records mirrored into backend `Stripe Terminal Payments`
- Backend refund flow for both backend-origin and POS-linked Stripe payments
- Odoo-aligned POS refunds for POS-linked Stripe payments
- Thermal HTML `Receipt` and `Refund` printing from `Stripe Terminal Payments`
- Optional webhooks for payment and refund sync
- Optional POS tip / gratuity support

---

## Current Flow Summary

### Backend flow

Use the **Stripe Terminal** top menu:

- `Stripe Terminal -> Payments -> New Payment`
- create a PaymentIntent
- start the reader payment
- check / capture the final result

### POS flow

Use a POS payment method configured with:

- `Use a Payment Terminal = Stripe Terminal (Orbit)`

If a Stripe `reader_id` is configured:

- POS prefers that configured reader
- Odoo drives the reader server-side
- this avoids the usual browser-side “reader must be on the same network” limitation

If no Stripe `reader_id` is configured:

- POS falls back to browser SDK reader discovery / connection
- in that mode the reader must be reachable from the POS device

### Refund flow

Refund Stripe Terminal payments from the backend:

- open the `Stripe Terminal Payments` record
- click `Issue Refund`

For POS-linked payments, the backend refund wizard:

- builds a real Odoo POS refund order
- creates the refund POS payment
- then sends the Stripe refund

This keeps POS totals, stock, and reporting aligned.

### Receipt flow

`Receipt` and `Refund` in `Stripe Terminal Payments` now open thermal HTML print pages.

- browser print dialog handles printing
- works for both `POS` and `Backend` source payments
- see [Printer Setup Guide](docs/PRINTER_SETUP_GUIDE.md)

---

## Quick Start Examples

The Docker commands below are examples only.

Replace these placeholders to match your environment:

- `YOUR_ODOO_SERVICE` = Docker Compose service that runs Odoo
- `YOUR_DB_NAME` = Odoo database name
- `YOUR_ODOO_SRC` = path inside the container that contains `odoo-bin`
- `YOUR_ODOO_CONF` = Odoo config file path or filename
- `YOUR_ODOO_BASE_URL` = your Odoo base URL

### 1. Build and start containers

```bash
docker compose up -d --build
```

### 2. Install the module for the first time

```bash
docker compose exec YOUR_ODOO_SERVICE bash -lc 'cd YOUR_ODOO_SRC && python3 odoo-bin -c YOUR_ODOO_CONF -d YOUR_DB_NAME -i orbit_stripe_contactless_payment --stop-after-init'
```

### 3. Upgrade after code changes

```bash
docker compose exec YOUR_ODOO_SERVICE bash -lc 'cd YOUR_ODOO_SRC && python3 odoo-bin -c YOUR_ODOO_CONF -d YOUR_DB_NAME -u orbit_stripe_contactless_payment --stop-after-init'
```

### 4. Start Odoo manually if your container does not auto-start it

Only needed in setups where the Odoo container does not already run the server process.

```bash
docker compose exec -d YOUR_ODOO_SERVICE bash -lc 'cd YOUR_ODOO_SRC && nohup python3 odoo-bin --config=YOUR_ODOO_CONF >/tmp/odoo.log 2>&1 &'
```

### 5. Open Odoo

```text
YOUR_ODOO_BASE_URL
```

### 6. Tail logs

```bash
docker compose logs -f YOUR_ODOO_SERVICE
```

---

## Configuration Checklist

### Stripe settings

Go to:

- `Settings -> Stripe Terminal`

Configure:

- `Test Mode`
- `Stripe Secret Key`
- `Stripe Publishable Key`
- `Terminal Location ID`
- `Stripe Reader ID` if you want a global reader
- `Webhook Secret` if you want verified webhook processing

Important:

- after changing `Test Mode`, click `Save`
- if POS is already open, close and reopen the POS so it reloads the new runtime config

### POS payment method

Go to:

- `Point of Sale -> Configuration -> Payment Methods`

Configure:

- `Use a Payment Terminal = Stripe Terminal (Orbit)`
- a GBP-compatible bank journal
- optional `Stripe Reader ID (Override)` if this payment method should always use one specific reader

Reader resolution order:

1. POS payment method override `reader_id`
2. Global Stripe reader from Settings
3. Browser SDK discovery if no configured reader exists

---

## Operational Notes

### Webhooks

Supported webhook endpoint:

- `/stripe/terminal/webhook`

Supported event handling includes:

- `payment_intent.succeeded`
- `payment_intent.payment_failed`
- `payment_intent.canceled`
- `charge.refunded`
- `terminal.reader.action_failed`

If a webhook secret is configured, the module verifies Stripe signatures.

### Refunds

For Stripe Terminal payments, use the backend refund flow from `Stripe Terminal Payments`.

For POS-linked refunds:

- an open POS session is required on the same POS configuration
- tracked lot/serial partial refunds may still need the native POS refund screen

### Thermal receipts

Current receipt printing is:

- thermal HTML
- browser print based
- not direct IoT / POS proxy printing

### Tap to Pay on iPhone / Android

This Odoo web module is designed around registered Stripe Terminal readers.

Tap to Pay on iPhone / Android requires Stripe’s native mobile SDK flow and is not provided by this Odoo web addon directly.

---

## HTTP Endpoints

| URL | Method | Auth | Purpose |
| --- | --- | --- | --- |
| `/stripe/terminal/connection_token` | POST | user session | Stripe Terminal connection token |
| `/stripe/terminal/webhook` | POST | none | Stripe webhook receiver |
| `/stripe/terminal/readers` | POST | user session | List readers for configured location |

---

## Folder Structure

```text
orbit_stripe_contactless_payment/
├── README.md
├── __manifest__.py
├── controllers/
├── data/
├── demo/
├── docs/
├── migrations/
├── models/
├── reports/
├── security/
├── services/
├── static/
└── views/
```

---

## Related Guides

- [Installation Guide](docs/INSTALLATION_GUIDE.md)
- [Live Mode Guide](docs/README_LIVE_MODE.md)
- [Printer Setup Guide](docs/PRINTER_SETUP_GUIDE.md)
- [Refund Guide](docs/REFUND_POLICY.md)
- [Refund Test Guide](docs/REFUND_TEST_GUIDE.md)
- [Webhook Guide](docs/WEBHOOK_SIMULATION_GUIDE.md)
- [Tip Setup Guide](docs/TIP_SETUP_GUIDE.md)
- [Debug and FAQ](docs/DEBUG_AND_FAQ.md)

---

## References

- [Stripe Terminal Docs](https://stripe.com/docs/terminal)
- [Stripe Terminal Readers](https://stripe.com/docs/terminal/readers)
- [Stripe Webhooks](https://stripe.com/docs/webhooks)
- [Stripe Python SDK](https://github.com/stripe/stripe-python)
- [Odoo 16 ORM Reference](https://www.odoo.com/documentation/16.0/developer/reference/backend/orm.html)

---

## Author

**Nazmus Shakib**  
Email: `nshakib.se@gmail.com`
