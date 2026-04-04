# Stripe Terminal — Live Mode Setup Guide (UK)

This guide walks you through going from test/simulation mode to **live production payments** in the UK, accepting contactless cards, Apple Pay (iOS), and Google Pay (Android).

---

## Prerequisites

- A **UK Stripe account** (live mode activated — submit business details in Stripe Dashboard)
- Odoo company **currency set to GBP** (Settings → Companies → Currency = British Pound)
- One of the following Stripe Terminal readers registered to your account:
  - **BBPOS WisePOS E** (countertop, Ethernet/WiFi)
  - **Stripe Reader S700** (countertop, Ethernet/WiFi)
  - **BBPOS Chipper 2X BT** (Bluetooth mobile)
  - **Stripe Reader M2** (Bluetooth mobile)
  - **Tap to Pay on iPhone** (no hardware — requires Stripe Terminal iOS SDK in a mobile app)
  - **Tap to Pay on Android** (no hardware — requires Stripe Terminal Android SDK in a mobile app)

---

## Step 1 — Activate Your Stripe Account for Live Mode

1. Log in to [https://dashboard.stripe.com](https://dashboard.stripe.com)
2. Click **Activate your account** in the top banner (if not already done)
3. Complete all business verification steps (business type, address, bank account, etc.)
4. Wait for Stripe to approve your account (usually instant for UK businesses)
5. Switch the Dashboard toggle from **Test** to **Live** (top-left corner)

---

## Step 2 — Get Your Live API Keys

1. In Stripe Dashboard (Live mode), go to **Developers → API Keys**
2. Copy your **Secret key**: `sk_live_...`
3. Copy your **Publishable key**: `pk_live_...`

> ⚠️ Never share your secret key. Never commit it to version control.

---

## Step 3 — Create a Terminal Location

Stripe requires a physical location for all Terminal readers.

1. In Stripe Dashboard → **Terminal → Locations**
2. Click **+ Add location**
3. Enter your business name and **UK address**
4. Click **Save** — copy the **Location ID** (`tml_...`)

---

## Step 4 — Register Your Reader

### Option A: Physical Reader (WisePOS E, S700, M2, Chipper 2X)

1. Power on your Stripe Terminal reader
2. In Stripe Dashboard → **Terminal → Readers → + Add reader**
3. Enter the **registration code** shown on the reader screen
4. Select the **Location** you created in Step 3
5. Give it a name and click **Register**
6. Copy the **Reader ID** (`tmr_...`)

### Option B: Tap to Pay on iPhone

- Requires a native iOS app using the **Stripe Terminal iOS SDK**
- The reader ID is assigned dynamically when the SDK discovers the device
- Follow: [https://stripe.com/docs/terminal/payments/setup-reader/tap-to-pay?platform=ios](https://stripe.com/docs/terminal/payments/setup-reader/tap-to-pay?platform=ios)

### Option C: Tap to Pay on Android

- Requires a native Android app using the **Stripe Terminal Android SDK**
- The reader ID is assigned dynamically when the SDK discovers the device
- Follow: [https://stripe.com/docs/terminal/payments/setup-reader/tap-to-pay?platform=android](https://stripe.com/docs/terminal/payments/setup-reader/tap-to-pay?platform=android)

---

## Step 5 — Configure Odoo Settings

1. In Odoo, go to **Settings → Stripe Terminal**
2. **Disable Test Mode** (toggle it OFF)
3. Enter your **Stripe Secret Key**: `sk_live_...`
4. Enter your **Stripe Publishable Key**: `pk_live_...`
5. Enter your **Terminal Location ID**: `tml_...`
6. Enter your **Stripe Reader ID**: `tmr_...`
7. Click **Save**

> When Test Mode is OFF and you use `sk_live_...`, the system will process **real payments**.

---

## Step 6 — Set Up a Webhook (Recommended)

Webhooks give you real-time payment confirmation without polling.

1. In Stripe Dashboard (Live mode) → **Developers → Webhooks → + Add endpoint**
2. Set the **Endpoint URL** to:
   ```
   https://YOUR-ODOO-DOMAIN.com/stripe/terminal/webhook
   ```
3. Select events to listen to:
   - `payment_intent.succeeded`
   - `payment_intent.payment_failed`
   - `payment_intent.canceled`
4. Click **Add endpoint**
5. Copy the **Webhook Secret** (`whsec_...`)
6. In Odoo → **Settings → Stripe Terminal → Webhook Secret** → paste it → Save

---

## Step 7 — Configure POS Payment Method

1. In Odoo, go to **Point of Sale → Configuration → Payment Methods**
2. Click **Create** (or edit an existing method)
3. Set **Name**: e.g. `Card / Contactless`
4. Set **Use a Payment Terminal**: `Stripe Terminal (Orbit)`
5. Optionally set a **Stripe Reader ID** to assign a specific reader to this payment method
   (leave blank to use the global reader from Settings)
6. Set the **Journal** to a bank journal with **Currency = GBP**
7. Click **Save**

---

## Step 8 — Assign Payment Method to Your POS

1. Go to **Point of Sale → Configuration → Settings**
2. Select your POS configuration
3. Under **Payment** → **Payment Methods**, add your new `Card / Contactless` method
4. Click **Save**

---

## Step 9 — Test a Live Payment

1. Open your POS session
2. Add products to an order
3. Click **Payment**
4. Select **Card / Contactless**
5. Click **Send** — the reader will prompt the customer
6. Customer taps their card, iPhone (Apple Pay), or Android phone (Google Pay)
7. Payment processes automatically

---

## Supported Contactless Payment Methods (UK)

| Method                       | Reader Required                                     | Notes        |
| ---------------------------- | --------------------------------------------------- | ------------ |
| Visa contactless             | Any Stripe Terminal reader                          | Physical tap |
| Mastercard contactless       | Any Stripe Terminal reader                          | Physical tap |
| American Express contactless | Any Stripe Terminal reader                          | Physical tap |
| Maestro contactless          | Any Stripe Terminal reader                          | Physical tap |
| Apple Pay (iPhone)           | Any Stripe Terminal reader OR Tap to Pay on iPhone  | NFC wallet   |
| Google Pay (Android)         | Any Stripe Terminal reader OR Tap to Pay on Android | NFC wallet   |
| Samsung Pay                  | Any Stripe Terminal reader                          | NFC wallet   |
| Other NFC wallets            | Any Stripe Terminal reader                          | NFC standard |

---

## Currency Note

> 🇬🇧 **UK Stripe accounts MUST use GBP.**
>
> The error `"The card_present source type with currency usd is not supported in GB"` means
> your Odoo company currency was set to USD. Fix: Settings → Companies → Currency → **British Pound (GBP)**.
>
> This addon automatically uses your Odoo company currency for all Stripe API calls.

---

## Troubleshooting

| Error                                                   | Cause                            | Fix                                                           |
| ------------------------------------------------------- | -------------------------------- | ------------------------------------------------------------- |
| `card_present with currency usd is not supported in GB` | Company currency is USD          | Set company currency to GBP                                   |
| `No readers discovered`                                 | Reader not registered or offline | Check reader is powered on and registered in Stripe Dashboard |
| `Reader not found`                                      | Wrong Reader ID                  | Copy `tmr_...` from Stripe Dashboard → Terminal → Readers     |
| `Invalid API key`                                       | Wrong key type vs mode           | Use `sk_live_...` in live mode, `sk_test_...` in test mode    |
| `Test mode enabled but live key provided`               | Mode/key mismatch                | Disable Test Mode in Settings before using live key           |
| `Terminal SDK failed to load`                           | No internet or CDN blocked       | Check network connectivity; allow `js.stripe.com`             |

---

## Security Checklist

- [ ] `sk_live_...` key stored only in Odoo Settings (never in code/git)
- [ ] Odoo server uses HTTPS
- [ ] Webhook endpoint uses HTTPS
- [ ] Webhook secret configured (prevents spoofed webhook events)
- [ ] Only Stripe Terminal Manager group users can access Settings

---

## Useful Links

- [Stripe Terminal UK overview](https://stripe.com/gb/terminal)
- [Stripe Terminal supported readers](https://stripe.com/docs/terminal/readers)
- [Tap to Pay on iPhone](https://stripe.com/docs/terminal/payments/setup-reader/tap-to-pay?platform=ios)
- [Tap to Pay on Android](https://stripe.com/docs/terminal/payments/setup-reader/tap-to-pay?platform=android)
- [Stripe Dashboard (Live)](https://dashboard.stripe.com)
- [Stripe Terminal API docs](https://stripe.com/docs/terminal)
