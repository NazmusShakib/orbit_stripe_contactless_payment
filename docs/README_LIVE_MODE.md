# Stripe Terminal — Live Mode Guide

Use this guide when moving the module from Stripe test mode to real production payments.

This document is for the current Odoo web addon flow.

---

## 1. What Live Mode Means Here

In live mode, this module uses:

- `sk_live_...`
- `pk_live_...`
- a live Stripe Terminal location
- a live registered Stripe reader

For the current Odoo web addon, the supported live flow is based on registered Stripe Terminal readers.

Important:

- Tap to Pay on iPhone / Android requires Stripe’s native mobile SDK flow and is not provided directly by this Odoo web addon

---

## 2. Before You Switch

Make sure:

- your Stripe account is fully activated
- your company currency is correct
- your payment journals are correct
- your reader is registered in the live Stripe account

For UK usage:

- set company currency to `GBP`
- use a GBP-compatible bank journal for the POS payment method

---

## 3. Activate Stripe Live Credentials

From Stripe Dashboard:

1. switch from `Test` to `Live`
2. open `Developers -> API keys`
3. copy:
   - `sk_live_...`
   - `pk_live_...`

Never store live keys in code or commit them to git.

---

## 4. Create the Live Terminal Location

In Stripe Dashboard:

1. go to `Terminal -> Locations`
2. create or choose the live location
3. copy the `tml_...` location ID

---

## 5. Register the Live Reader

In Stripe Dashboard:

1. go to `Terminal -> Readers`
2. add or confirm the physical reader
3. copy the `tmr_...` reader ID

Recommended live use for this addon:

- WisePOS E
- Stripe Reader S700
- other Stripe Terminal readers that are registered and online in your Stripe account

---

## 6. Configure Odoo Settings

Go to:

- `Settings -> Stripe Terminal`

Set:

- `Test Mode = OFF`
- `Stripe Secret Key = sk_live_...`
- `Stripe Publishable Key = pk_live_...`
- `Terminal Location ID = tml_...`
- `Stripe Reader ID = tmr_...` if you want a global default reader

Then:

1. click `Save`
2. close any open POS sessions/tabs
3. reopen the POS so it reloads live runtime config

---

## 7. Configure the POS Payment Method

Go to:

- `Point of Sale -> Configuration -> Payment Methods`

For the Stripe Terminal payment method:

- `Use a Payment Terminal = Stripe Terminal (Orbit)`
- choose the correct bank journal
- optionally set `Stripe Reader ID (Override)`

Reader resolution order:

1. payment method override reader
2. global Settings reader
3. browser SDK discovery if no configured reader is available

If you want stable live behavior, configure a reader ID either:

- globally in Settings
- or on the payment method override

That lets Odoo drive the reader server-side.

---

## 8. Recommended Live Setup

For this addon, the cleanest live setup is:

- live Stripe keys in Settings
- live `tml_...` location
- configured live `tmr_...` reader
- payment method override only if you want dedicated readers per POS method

This avoids depending on browser-side reader discovery.

---

## 9. Optional Webhook Setup

Recommended webhook endpoint:

```text
https://DOMAIN/stripe/terminal/webhook
```

Recommended events:

- `payment_intent.succeeded`
- `payment_intent.payment_failed`
- `payment_intent.canceled`
- `charge.refunded`
- `terminal.reader.action_failed`

Then:

1. copy the `whsec_...` secret from Stripe
2. paste it into `Settings -> Stripe Terminal -> Webhook Secret`
3. save

With a webhook secret configured, the module verifies Stripe signatures.

---

## 10. Live Payment Test Checklist

Do a small real payment before full rollout.

### Backend

1. open `Stripe Terminal -> Payments -> New Payment`
2. create a small payment
3. click `1. Create Payment Intent`
4. click `2. Start Reader Payment`
5. click `3. Check / Capture Payment`
6. confirm the record reaches `Succeeded`

### POS

1. open the POS session
2. add a low-value product
3. choose the Stripe Terminal payment method
4. complete the payment
5. confirm:
   - POS order is paid
   - backend `Stripe Terminal Payments` record exists
   - Stripe Dashboard shows the live payment

---

## 11. Live Refund Test Checklist

After a successful live payment:

1. open the backend `Stripe Terminal Payments` record
2. click `Issue Refund`
3. complete a small partial or full refund
4. confirm:
   - Stripe Dashboard shows the refund
   - Odoo backend record updates
   - for POS-linked payments, the refund creates the real POS refund order/payment

For POS-linked refunds:

- the same POS configuration must have an open session

---

## 12. Common Live-Mode Issues

### Payment still behaves like test mode

Cause:

- POS was already open when settings changed

Fix:

1. save settings
2. close the POS tab
3. reopen the POS session

### Reader not found

Cause:

- wrong `tmr_...`
- reader registered in test account but not live account

Fix:

- copy the live reader ID from live Stripe Dashboard

### Same-network discovery error

Cause:

- no configured reader ID, so POS fell back to browser discovery

Fix:

- set a global reader ID in Settings or a payment method override reader

### Webhook signature errors

Cause:

- wrong `whsec_...`
- test webhook secret used in live mode

Fix:

- copy the live webhook secret from the live Stripe endpoint

---

## 13. Live Go-Live Checklist

- live Stripe account activated
- `Test Mode` is OFF
- live keys saved
- live location ID saved
- live reader ID saved
- POS payment method configured
- POS reopened after settings change
- one backend test payment done
- one POS test payment done
- one refund test done
- webhook secret configured
- printer tested for `Receipt` and `Refund`

---

## 14. Related Guides

- [README.md](../README.md)
- [INSTALLATION_GUIDE.md](INSTALLATION_GUIDE.md)
- [REFUND_POLICY.md](REFUND_POLICY.md)
- [PRINTER_SETUP_GUIDE.md](PRINTER_SETUP_GUIDE.md)
- [WEBHOOK_SIMULATION_GUIDE.md](WEBHOOK_SIMULATION_GUIDE.md)
