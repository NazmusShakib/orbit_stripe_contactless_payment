# Stripe Terminal Payment — Installation & Setup Guide

Complete guide for installing and configuring contactless card payments in Odoo 16 (UK).

Accepts: **Visa · Mastercard · Amex · Maestro · Apple Pay (iOS) · Google Pay (Android) · Samsung Pay · All NFC wallets**

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Installation](#2-installation)
3. [Test Mode Setup (Development)](#3-test-mode-setup-development)
4. [Live Mode Setup (Production)](#4-live-mode-setup-production)
5. [POS Configuration](#5-pos-configuration)
6. [Taking a Payment](#6-taking-a-payment)
7. [Webhook Setup (Optional but Recommended)](#7-webhook-setup)
8. [Supported Readers](#8-supported-readers)
9. [Troubleshooting](#9-troubleshooting)
10. [Security Checklist](#10-security-checklist)

---

## 1. Prerequisites

### System Requirements

- Odoo 16.0 (Community or Enterprise)
- Python 3.8+
- PostgreSQL 12+
- Internet access from the Odoo server (for Stripe API calls)
- HTTPS enabled on your Odoo server (required for Stripe Terminal JS SDK)

### Stripe Account Requirements

- A [Stripe account](https://stripe.com/gb) registered in the **United Kingdom**
- Stripe Terminal enabled for your account (go to Dashboard → Terminal)
- For live payments: business verification completed in Stripe Dashboard

### Python Package

```bash
pip install stripe
```

Or add to your `requirements.txt`:

```
stripe>=5.0.0
```

---

## 2. Installation

### Step 1 — Copy the module

Place the `orbit_stripe_contactless_payment` folder in your Odoo addons path.

For Docker setups, ensure the path is mounted:

```yaml
# docker-compose.yml example
volumes:
  - ./custom/addons:/app/custom/addons
```

Verify the addons path in `odoo.conf`:

```ini
addoorbit_path = /app/odoo-server/addons,/app/custom/addons
```

### Step 2 — Install Python dependency

```bash
pip install stripe
```

### Step 3 — Restart Odoo

```bash
# Docker example
docker exec -d odoo_container python3 /app/odoo-server/odoo-bin \
  -c /app/odoo-server/odoo-server.conf
```

### Step 4 — Install the module in Odoo

1. Go to **Apps** (enable developer mode if needed: Settings → Activate Developer Mode)
2. Search for **"Orbit Stripe Terminal"**
3. Click **Install**

> If not visible: click **Update Apps List** first (Apps → Update Apps List)

### Step 5 — Upgrade (if already installed)

```bash
docker exec odoo_container python3 /app/odoo-server/odoo-bin \
  -c /app/odoo-server/odoo-server.conf \
  -d YOUR_DATABASE_NAME \
  -u orbit_stripe_contactless_payment \
  --stop-after-init
```

---

## 3. Test Mode Setup (Development)

Use test mode to develop and test without processing real payments.
Stripe provides simulated readers that behave exactly like real hardware.

### Step 1 — Get Test API Keys

1. Log in to [Stripe Dashboard](https://dashboard.stripe.com)
2. **Toggle to Test Mode** (top-left switch — must show "Test")
3. Go to **Developers → API Keys**
4. Copy:
   - **Secret key**: `sk_test_51...`
   - **Publishable key**: `pk_test_51...`

### Step 2 — Create a Terminal Location

1. Stripe Dashboard (test mode) → **Terminal → Locations**
2. Click **+ Add location**
3. Enter your business name and address (UK address for GBP)
4. Click **Save** — copy the **Location ID**: `tml_...`

### Step 3 — Configure in Odoo

1. Go to **Settings → Stripe Terminal**
2. Enable **Test Mode**
3. Enter **Stripe Secret Key**: `sk_test_...`
4. Enter **Stripe Publishable Key**: `pk_test_...`
5. Enter **Terminal Location ID**: `tml_...`
6. Leave **Reader ID** blank for now
7. Click **Save**

### Step 4 — Create a Simulated Reader

1. In **Settings → Stripe Terminal**, click **Open Setup and Test Wizard**
2. Click **Test Connection** — should show Connected
3. Click **Create Simulated Reader**
4. The Reader ID (`tmr_...`) is automatically saved to Settings
5. Note the Reader ID for reference

> Alternatively, create via Stripe Dashboard (test mode):
> Terminal → Readers → + Add reader → Simulated → copy `tmr_...`

### Step 5 — Set Company Currency Inside Odoo

> ⚠️ **Critical for UK accounts** — Stripe Terminal in GB requires GBP.

1. Go to **Settings → Companies → [Your Company]**
2. Set **Currency** to **British Pound (£) GBP**
3. Click **Save**

---

## 4. Live Mode Setup (Production)

### Step 1 — Activate Your Stripe Account

1. Log in to [Stripe Dashboard](https://dashboard.stripe.com)
2. Click **Activate account** and complete all verification steps
3. Switch the Dashboard toggle from **Test** to **Live**

### Step 2 — Get Live API Keys

1. Stripe Dashboard (live mode) → **Developers → API Keys**
2. Copy:
   - **Secret key**: `sk_live_...`
   - **Publishable key**: `pk_live_...`

> ⚠️ Never share your live secret key. Never commit it to version control.

### Step 3 — Create a Live Terminal Location

1. Stripe Dashboard (live mode) → **Terminal → Locations → + Add location**
2. Enter your actual UK business name and address
3. Save — copy **Location ID**: `tml_...`

### Step 4 — Register Your Physical Reader

**Option A: Countertop readers (WisePOS E, S700)**

1. Power on the reader
2. Stripe Dashboard → **Terminal → Readers → + Add reader**
3. Enter the **registration code** shown on the reader display
4. Select your location, give it a name, click **Register**
5. Copy the **Reader ID**: `tmr_...`

**Option B: Bluetooth readers (Chipper 2X BT, M2)**

- Pair with your device using the Stripe Terminal mobile SDK
- The reader ID appears in the SDK and Stripe Dashboard

**Option C: Tap to Pay on iPhone**

- Requires a native iOS app with Stripe Terminal iOS SDK
- No hardware needed — the iPhone itself becomes the reader
- Follow: https://stripe.com/docs/terminal/payments/setup-reader/tap-to-pay?platform=ios

**Option D: Tap to Pay on Android**

- Requires a native Android app with Stripe Terminal Android SDK
- No hardware needed — the Android device becomes the reader
- Follow: https://stripe.com/docs/terminal/payments/setup-reader/tap-to-pay?platform=android

### Step 5 — Configure Odoo for Live Mode

1. Go to **Settings → Stripe Terminal**
2. **Disable Test Mode** (toggle OFF)
3. Enter **Stripe Secret Key**: `sk_live_...`
4. Enter **Stripe Publishable Key**: `pk_live_...`
5. Enter **Terminal Location ID**: `tml_...` (live)
6. Enter **Stripe Reader ID**: `tmr_...` (live reader)
7. Click **Save**

---

## 5. POS Configuration

### Step 1 — Ensure Company Currency is GBP

**Settings → Companies → [Your Company] → Currency = British Pound (GBP)**

### Step 2 — Create a Bank Journal for Card Payments

1. **Accounting → Configuration → Journals → New**
2. **Name**: `Stripe Terminal` (or `Card Payments`)
3. **Type**: `Bank`
4. **Currency**: `GBP`
5. Save

> If you already have a Bank/GBP journal, you can use it directly.

### Step 3 — Create the POS Payment Method

1. **Point of Sale → Configuration → Payment Methods → New**
2. **Name**: `Card / Contactless`
3. **Journal**: Select your GBP Bank journal (e.g. `Stripe Terminal`)
4. **Use a Payment Terminal**: Select **`Stripe Terminal (Orbit)`**
5. **Stripe Reader ID (Override)**: Leave blank (uses global setting) OR enter a specific `tmr_...` to assign a dedicated reader
6. Click **Save**

> ⚠️ The "Use a Payment Terminal" dropdown only appears on **Bank-type** payment methods (not Cash). Make sure you selected a Bank journal.

### Step 4 — Add to Your POS Configuration

1. **Point of Sale → Configuration → Settings**
2. Select your POS
3. Under **Payments → Payment Methods**: add `Card / Contactless`
4. Click **Save**

---

## 6. Taking a Payment

### In the POS

1. Open a POS session
2. Add products to the order
3. Click **Payment**
4. Click **Card / Contactless** (or your payment method name)
5. Enter the amount (or it auto-fills)
6. Click **Send / Validate**
7. The reader prompts the customer to tap

**Customer taps one of:**

- 💳 Physical contactless card
- 📱 iPhone with Apple Pay
- 📱 Android phone with Google Pay
- 📱 Samsung Pay or other NFC wallet

8. Payment processes automatically
9. POS shows payment as done

### In the Backend (Stripe Terminal Payments menu)

1. Go to **Point of Sale → Stripe Terminal Payments** (or the Orbit menu)
2. Click **New**
3. Enter amount and description
4. Click **Create Payment Intent**
5. Click **Simulate/Collect Payment** (test) or **Collect Payment** (live)
6. Click **Confirm Payment**

---

## 7. Webhook Setup

Webhooks give real-time payment confirmation. Without webhooks, the POS relies on the SDK response; with webhooks, the backend Odoo record updates automatically too.

### Step 1 — Add Webhook in Stripe Dashboard

1. Stripe Dashboard → **Developers → Webhooks → + Add endpoint**
2. **Endpoint URL**:
   ```
   https://YOUR-ODOO-DOMAIN.com/stripe/terminal/webhook
   ```
3. **Events to send**:
   - `payment_intent.succeeded`
   - `payment_intent.payment_failed`
   - `payment_intent.canceled`
   - `terminal.reader.action_failed`
4. Click **Add endpoint**
5. Copy the **Webhook signing secret**: `whsec_...`

### Step 2 — Configure in Odoo

1. **Settings → Stripe Terminal → Webhook Secret**: paste `whsec_...`
2. Click **Save**

> Use separate webhook endpoints for test and live (different `whsec_...` secrets).

---

## 8. Supported Readers

| Reader                | Type        | Connection      | UK Available |
| --------------------- | ----------- | --------------- | ------------ |
| BBPOS WisePOS E       | Countertop  | Ethernet / WiFi | True         |
| Stripe Reader S700    | Countertop  | Ethernet / WiFi | True         |
| BBPOS Chipper 2X BT   | Mobile      | Bluetooth       | True         |
| Stripe Reader M2      | Mobile      | Bluetooth       | True         |
| Tap to Pay on iPhone  | iOS app     | No hardware     | True         |
| Tap to Pay on Android | Android app | No hardware     | True         |

All readers accept:

- 💳 Visa, Mastercard, Amex, Maestro (physical contactless)
- 📱 Apple Pay (iPhone / Apple Watch)
- 📱 Google Pay (Android)
- 📱 Samsung Pay
- 📱 Any NFC-enabled payment wallet

---

## 9. Troubleshooting

### `card_present with currency usd is not supported in GB`

**Cause**: Odoo company currency is set to USD, not GBP.
**Fix**: Settings → Companies → [Your Company] → Currency → **British Pound (GBP)**

### `No Stripe readers were discovered`

**Test mode fix**:

- Ensure a simulated reader exists in Stripe Dashboard (test) → Terminal → Readers
- The reader must be at the same Location ID configured in Settings
- Use the Setup Wizard to create one automatically

**Live mode fix**:

- Ensure reader is powered on and connected to the network
- Ensure reader is registered in Stripe Dashboard → Terminal → Readers
- Ensure reader location matches the Location ID in Settings

### `Stripe Terminal SDK failed to load`

- Check your browser can reach `js.stripe.com` (not blocked by firewall/proxy)
- Check browser console for network errors
- Ensure your Odoo server uses HTTPS (Stripe SDK requires HTTPS in production)

### `Invalid API key`

- Check you're using `sk_test_...` in Test Mode and `sk_live_...` in Live Mode
- The key must belong to your UK Stripe account

### `Test Mode is OFF but a test key was provided`

- Either enable Test Mode in Settings, or switch to your `sk_live_...` key

### `Use a Payment Terminal` dropdown not visible

- The journal must be type **Bank** (not Cash)
- If bank journal is selected and still hidden: hard refresh browser (Ctrl+Shift+R)
- Ensure the module is installed (not just activated)

### `All payment methods must be in the same currency as the Sales Journal`

- The Bank journal currency must match the company currency (both GBP)
- Set the journal currency to GBP: Accounting → Journals → [journal] → Currency = GBP

### Currency mismatch after changing company currency

- After changing company currency to GBP, restart Odoo to clear the cache
- Hard refresh the browser

---

## 10. Security Checklist

Before going live, verify:

- [ ] Odoo server uses **HTTPS** (required for Stripe Terminal SDK)
- [ ] `sk_live_...` key is stored **only in Odoo Settings** — never in code or git
- [ ] **Webhook Secret** is configured (prevents spoofed webhook events)
- [ ] Only users in **Stripe Terminal Manager** group can access Settings
- [ ] POS users can take payments but cannot access API key settings
- [ ] Regular Stripe Dashboard audit: check for unexpected payments
- [ ] Set up Stripe **Radar rules** for fraud prevention
- [ ] Enable **Two-factor authentication** on your Stripe account

---

## Module Structure

```
orbit_stripe_contactless_payment/
├── __manifest__.py              # Module metadata and dependencies
├── models/
│   ├── pos_payment_method.py    # POS terminal registration + RPC methods
│   ├── pos_session.py           # Injects Stripe config into POS frontend
│   ├── res_config_settings.py   # Settings fields
│   ├── stripe_terminal_payment.py # Backend payment records
│   └── stripe_setup_wizard.py   # Setup wizard
├── services/
│   └── stripe_terminal_service.py # All Stripe API calls
├── controllers/
│   └── main.py                  # HTTP endpoints (connection token, webhook)
├── static/src/js/
│   ├── payment_orbit_stripe.js  # POS JavaScript payment handler
│   └── models_orbit_stripe.js   # Registers payment method with POS
├── views/
│   ├── pos_payment_method_views.xml  # POS payment method form
│   ├── assets_orbit_stripe.xml       # Stripe SDK CDN script
│   ├── res_config_settings_views.xml # Settings UI
│   └── ...
├── migrations/
│   └── 16.0.1.1.0/pre-migrate.py   # Adds orbit_stripe_reader_id column
├── IOrbitTALLATION_GUIDE.md        # This file
└── README_LIVE_MODE.md          # Quick live mode reference
```

---

## Quick Reference — Key Settings

| Setting          | Test Mode Value       | Live Mode Value           |
| ---------------- | --------------------- | ------------------------- |
| Test Mode toggle | ON                    | OFF                       |
| Secret Key       | `sk_test_...`         | `sk_live_...`             |
| Publishable Key  | `pk_test_...`         | `pk_live_...`             |
| Location ID      | `tml_...` (test)      | `tml_...` (live)          |
| Reader ID        | `tmr_...` (simulated) | `tmr_...` (real hardware) |
| Webhook Secret   | `whsec_...` (test)    | `whsec_...` (live)        |
| Company Currency | GBP                   | GBP                       |
| Journal Type     | Bank                  | Bank                      |
| Journal Currency | GBP                   | GBP                       |

---

## Support & Links

- [Stripe Terminal UK Overview](https://stripe.com/gb/terminal)
- [Stripe Terminal Readers](https://stripe.com/docs/terminal/readers)
- [Stripe Terminal JS SDK Docs](https://stripe.com/docs/terminal/references/sdk/js)
- [Tap to Pay on iPhone](https://stripe.com/docs/terminal/payments/setup-reader/tap-to-pay?platform=ios)
- [Tap to Pay on Android](https://stripe.com/docs/terminal/payments/setup-reader/tap-to-pay?platform=android)
- [Stripe Dashboard (Test)](https://dashboard.stripe.com/test)
- [Stripe Dashboard (Live)](https://dashboard.stripe.com)
- [Stripe Webhook Docs](https://stripe.com/docs/webhooks)
