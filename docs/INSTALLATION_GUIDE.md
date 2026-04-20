# Stripe Terminal Payment — Installation Guide

This guide is written for the module itself, not one specific repo layout.

If you use Docker Compose, replace these placeholders to match your setup:

- `YOUR_ODOO_SERVICE` = Compose service that runs Odoo
- `YOUR_DB_SERVICE` = Compose service that runs PostgreSQL
- `YOUR_DB_NAME` = Odoo database name
- `YOUR_ODOO_SRC` = path inside the container that contains `odoo-bin`
- `YOUR_ODOO_CONF` = Odoo config file path or filename
- `YOUR_ODOO_BASE_URL` = your Odoo base URL

---

## 1. Prerequisites

Before installing the module, make sure you have:

- Docker and Docker Compose available
- a Stripe account
- Stripe API keys
- a Stripe Terminal location ID (`tml_...`)
- a Stripe reader ID (`tmr_...`) if you want to use a configured reader

For UK usage:

- company currency and payment journal currency should be `GBP`

---

## 2. Start the Project Containers

From your project root:

```bash
docker compose up -d --build
```

If your Odoo container already starts the server automatically, you can skip the manual start step below.

---

## 3. Install or Upgrade the Module

### First install

```bash
docker compose exec YOUR_ODOO_SERVICE bash -lc 'cd YOUR_ODOO_SRC && python3 odoo-bin -c YOUR_ODOO_CONF -d YOUR_DB_NAME -i orbit_stripe_contactless_payment --stop-after-init'
```

### Upgrade after code changes

```bash
docker compose exec YOUR_ODOO_SERVICE bash -lc 'cd YOUR_ODOO_SRC && python3 odoo-bin -c YOUR_ODOO_CONF -d YOUR_DB_NAME -u orbit_stripe_contactless_payment --stop-after-init'
```

---

## 4. Start Odoo

```bash
docker compose exec -d YOUR_ODOO_SERVICE bash -lc 'cd YOUR_ODOO_SRC && nohup python3 odoo-bin --config=YOUR_ODOO_CONF >/tmp/odoo.log 2>&1 &'
```

Then open:

```text
YOUR_ODOO_BASE_URL
```

If you need logs:

```bash
docker compose logs -f YOUR_ODOO_SERVICE
```

---

## 5. Configure Stripe Terminal Settings

Go to:

- `Settings -> Stripe Terminal`

Set:

- `Test Mode`
- `Stripe Secret Key`
- `Stripe Publishable Key`
- `Terminal Location ID`
- `Stripe Reader ID` if you want a global reader
- `Webhook Secret` if you plan to use Stripe webhooks

### Test mode

Use:

- `sk_test_...`
- `pk_test_...`

You can create a simulated reader from:

- `Settings -> Stripe Terminal -> Open Setup and Test Wizard`

### Live mode

Use:

- `sk_live_...`
- `pk_live_...`

Use a real registered Stripe reader ID:

- `tmr_...`

Important:

- click `Save` after changing mode or keys
- if POS is already open, close and reopen it so the runtime config reloads

---

## 6. Configure the POS Payment Method

Go to:

- `Point of Sale -> Configuration -> Payment Methods`

Create or edit a payment method:

- `Use a Payment Terminal = Stripe Terminal (Orbit)`
- choose a GBP-compatible bank journal
- optional `Stripe Reader ID (Override)` if this payment method should always use one specific reader

Reader selection order:

1. payment method override
2. global Settings reader
3. browser SDK discovery if no configured reader exists

---

## 7. Assign the Payment Method to a POS

Go to:

- `Point of Sale -> Configuration -> Settings`

For the POS configuration:

- add the `Card / Contactless` payment method
- save

If the POS was already open:

- close the tab
- hard refresh
- reopen the session

---

## 8. Verify the Backend Flow

Use:

- `Stripe Terminal -> Payments -> New Payment`

Test sequence:

1. Enter amount and description
2. Click `1. Create Payment Intent`
3. Click `2. Simulate Card Tap` in test mode or `2. Start Reader Payment` in live mode
4. Click `3. Check / Capture Payment`
5. Confirm the record reaches `Succeeded`

You should also be able to:

- click `Receipt`
- click `Issue Refund` on succeeded payments

---

## 9. Verify the POS Flow

Open the POS session and take a payment using the Stripe Terminal payment method.

Expected behavior:

- if a configured reader ID exists, Odoo drives that reader directly
- the POS payment is mirrored into `Stripe Terminal Payments`
- the backend record stores the PaymentIntent, charge, source, POS references, and refund history

---

## 10. Assets and Browser Refresh

After changing Python or XML:

- run the module upgrade command

After changing JS, XML under `static/`, or receipt templates:

1. upgrade the module
2. hard refresh the browser with `Ctrl+Shift+R` or `Cmd+Shift+R`
3. reopen POS if it was already open

---

## 11. Current Operational Notes

### Refunds

Stripe Terminal refunds are handled from the backend `Stripe Terminal Payments` flow.

For POS-linked payments, the backend refund wizard:

- creates a real Odoo POS refund order
- creates the refund POS payment
- then sends the Stripe refund

For those POS-linked refunds:

- the same POS configuration must have an open session

### Receipts

`Receipt` and `Refund` open thermal HTML pages for browser printing.

See:

- [PRINTER_SETUP_GUIDE.md](PRINTER_SETUP_GUIDE.md)

### Webhooks

Webhooks are optional but recommended for:

- out-of-band dashboard refunds
- automatic backend record updates
- payment state synchronization

See:

- [WEBHOOK_SIMULATION_GUIDE.md](WEBHOOK_SIMULATION_GUIDE.md)

---

## 12. Useful Commands

### Odoo shell

```bash
docker compose exec YOUR_ODOO_SERVICE bash -lc 'cd YOUR_ODOO_SRC && python3 odoo-bin shell -c YOUR_ODOO_CONF -d YOUR_DB_NAME --no-http'
```

### PostgreSQL shell

```bash
docker compose exec YOUR_DB_SERVICE psql -U YOUR_DB_USER -d YOUR_DB_NAME
```

### Tail Odoo logs

```bash
docker compose logs -f YOUR_ODOO_SERVICE
```

---

## 13. Related Guides

- [README.md](../README.md)
- [README_LIVE_MODE.md](README_LIVE_MODE.md)
- [PRINTER_SETUP_GUIDE.md](PRINTER_SETUP_GUIDE.md)
- [REFUND_POLICY.md](REFUND_POLICY.md)
- [WEBHOOK_SIMULATION_GUIDE.md](WEBHOOK_SIMULATION_GUIDE.md)
- [DEBUG_AND_FAQ.md](DEBUG_AND_FAQ.md)
