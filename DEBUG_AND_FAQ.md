# Stripe Terminal — Debug Guide & FAQ

Everything you need to troubleshoot, monitor, and resolve issues for cashiers, managers, and developers.

---

## Table of Contents

1. [Where to See Transaction Logs](#1-where-to-see-transaction-logs)
2. [Common Issues — Cashier / Customer Facing](#2-common-issues--cashier--customer-facing)
3. [Common Issues — Technical / Developer](#3-common-issues--technical--developer)
4. [Common Issues — Refunds](#4-common-issues--refunds)
5. [Debug Checklist](#5-debug-checklist)
6. [Understanding Error Codes](#6-understanding-error-codes)

---

## 1. Where to See Transaction Logs

There are **5 places** to see transaction data — from simplest to most detailed.

---

### 📍 1A — Odoo Backend (Easiest)

**Point of Sale → Stripe Terminal Payments**

Shows every payment record with full status:

| Column        | What it shows                         |
| ------------- | ------------------------------------- |
| Reference     | `STP/2026/00001` — Odoo internal ref  |
| Amount        | £25.00                                |
| Currency      | GBP                                   |
| Status        | Draft / Succeeded / Refunded / Failed |
| Stripe PI ID  | `pi_3TFqVtK4sPO78s171m6XQ9hJ`         |
| Refund ID     | `re_3TFsAj...` (if refunded)          |
| Refund Amount | £8.00 (partial)                       |
| Created       | Date/time                             |

**Click any record** to see:

- Full chatter history (every action logged with timestamp)
- Stripe PaymentIntent ID (click to open in Stripe Dashboard)
- Refund details
- Error messages if failed

**Live records from your system:**

```
STP/2026/00002 | £5.00  | succeeded | pi_3TFqtdK4sPO78s170IZaQWC6
STP/2026/00001 | £25.00 | succeeded | pi_3TFqVtK4sPO78s171m6XQ9hJ
```

---

### 📍 1B — Stripe Dashboard (Most Complete)

**https://dashboard.stripe.com/test/payments** (test mode)
**https://dashboard.stripe.com/payments** (live mode)

Shows every charge processed through your Stripe account:

**Payments list** — filter by date, amount, status, card brand
**Click any payment** to see:

- Exact timestamp
- Card brand and last 4 digits
- Payment method (card / Apple Pay / Google Pay)
- Capture method
- All refunds with individual amounts
- Webhook events sent
- Full metadata (Odoo reference, user, company)

**Search tips:**

```
Search by PaymentIntent:  pi_3TFqVt...
Search by Charge:         ch_3TFqVt...
Search by amount:         25.00
Search by last4:          4242
```

---

### 📍 1C — Stripe Dashboard — Developers → Logs

**https://dashboard.stripe.com/test/logs**

Shows every raw API call your Odoo server made to Stripe:

| Column   | Example             |
| -------- | ------------------- |
| Method   | POST                |
| Endpoint | /v1/payment_intents |
| Status   | 200 OK              |
| Time     | 2026-03-28 08:24    |
| Duration | 342ms               |

**Click any log entry** → full JSON request + response body.

**Filter by endpoint:**

- `/v1/payment_intents` → payment creation
- `/v1/payment_intents/pi_.../capture` → captures
- `/v1/refunds` → refunds
- `/v1/terminal/readers` → reader operations
- `/v1/terminal/connection_tokens` → SDK connection tokens

---

### 📍 1D — Stripe Dashboard — Developers → Events

**https://dashboard.stripe.com/test/events**

Shows every webhook event Stripe sent (or tried to send):

| Event                           | When                  |
| ------------------------------- | --------------------- |
| `payment_intent.created`        | PaymentIntent created |
| `payment_intent.succeeded`      | Payment captured      |
| `payment_intent.payment_failed` | Card declined         |
| `payment_intent.canceled`       | Cashier cancelled     |
| `charge.refunded`               | Refund issued         |
| `terminal.reader.action_failed` | Reader error          |

**Click any event** → full JSON payload + delivery attempts to your webhook URL.

---

### 📍 1E — Browser Console (Real-Time POS)

Open **F12** in Chrome/Firefox while POS is open.
Click **Console** tab. Filter: `[OrbitStripe]`

Every step logged in real-time:

```
[OrbitStripe] ━━━ PAYMENT FLOW START ━━━
[OrbitStripe] Amount: 25 | testMode: true

▶ [OrbitStripe] ⏳ Step 1: Create PaymentIntent (server → Stripe API)
  [OrbitStripe] → RPC Request: orbit_stripe_payment_intent {"amount": 25}
  [OrbitStripe] ← RPC Response: {
    "id": "pi_3TFqVtK4sPO78s171m6XQ9hJ",
    "status": "requires_payment_method",
    "amount": 2500,
    "currency": "gbp"
  }

▶ [OrbitStripe] 🔌 Step 2: collectPaymentMethod (SDK → Reader)
  [OrbitStripe] [TEST MODE] Card tap simulated automatically
  [OrbitStripe] collectPaymentMethod SUCCESS. Status: requires_capture

▶ [OrbitStripe] 💳 Step 3: processPayment (SDK → Stripe API)
  [OrbitStripe] processPayment SUCCESS. Status: requires_capture

▶ [OrbitStripe] ⚡ Step 4: Capture (server → Stripe API)
  [OrbitStripe] Capture SUCCESS. Status: succeeded | charge: ch_3TFqVt...
  [OrbitStripe] Card brand: visa | last4: 4242 | funding: credit | country: US

[OrbitStripe] ━━━ PAYMENT FLOW COMPLETE ━━━
[OrbitStripe] transaction_id: pi_3TFqVtK4sPO78s171m6XQ9hJ
[OrbitStripe] card_type: visa
```

---

### 📍 1F — Odoo Server Logs (Python/Backend)

**Live tail:**

```bash
docker logs odoo16_app -f 2>&1 | grep -i stripe
```

**In log file:**

```bash
docker exec odoo16_app tail -f /app/odoo-server/log/odoo/odoo-server.log | grep -i stripe
```

**What you see:**

```
INFO orbit_stripe_contactless_payment.models.pos_payment_method:
  POS PaymentIntent: method=Card amount=25.0 gbp (2500 units)

INFO orbit_stripe_contactless_payment.services.stripe_terminal_service:
  Creating PaymentIntent: amount=2500 gbp, types=['card_present'], capture=manual

INFO orbit_stripe_contactless_payment.services.stripe_terminal_service:
  PaymentIntent created: pi_3TFqVt... (status=requires_payment_method)

INFO orbit_stripe_contactless_payment.models.pos_payment_method:
  Capturing POS PaymentIntent: pi_3TFqVt... (amount_int=None)

INFO orbit_stripe_contactless_payment.services.stripe_terminal_service:
  Capturing PaymentIntent: pi_3TFqVt... (amount=None)

INFO orbit_stripe_contactless_payment.models.pos_payment_method:
  Captured. Charge: ch_3TFqVt... | brand: visa | last4: 4242 | funding: credit

INFO orbit_stripe_contactless_payment.models.pos_payment_method:
  POS PaymentIntent pi_3TFqVt... captured successfully. Status: succeeded
```

**Filter for errors only:**

```bash
docker logs odoo16_app 2>&1 | grep -E "(ERROR|error.*stripe|Stripe.*error)" | tail -20
```

---

### 📍 1G — PostgreSQL Database (Raw Data)

```bash
docker exec odoo16_pg14 psql -U odoo -d odoo_16_dummy -c "
SELECT name, state, amount, stripe_payment_intent_id,
       stripe_refund_id, refund_amount, create_date
FROM stripe_terminal_payment
ORDER BY create_date DESC LIMIT 20;
"
```

---

## 2. Common Issues — Cashier / Customer Facing

These are issues that happen during a sale or refund at the till.

---

### ❌ "No readers discovered"

**What the cashier sees:** Error popup — "No Stripe readers found"

**Cause A — Test mode, no simulated reader set up**

- Fix: Go to **Settings → Stripe Terminal → Open Setup Wizard → Create Simulated Reader**

**Cause B — Live mode, reader is offline**

- Fix: Check the reader is powered on and its screen shows "Ready"
- Check it's connected to the same WiFi/network as the Odoo server
- Restart the reader (hold power button 10 seconds)

**Cause C — Reader not registered in Stripe**

- Fix: Stripe Dashboard → Terminal → Readers → check reader is listed and status = Online

**Cause D — Wrong Location ID in Settings**

- Fix: Settings → Stripe Terminal → Location ID must match the reader's assigned location in Stripe Dashboard

---

### ❌ "Card declined"

**What the customer sees:** Card reader shows "Declined" or beeps

**Common reasons:**
| Reason | Fix |
|--------|-----|
| Insufficient funds | Customer uses different card |
| Card expired | Customer uses different card |
| Contactless limit exceeded | Ask customer to insert card + PIN |
| Bank blocked the transaction | Customer calls their bank |
| Card damaged/chip issue | Try different card |

**In test mode — simulate a decline:**
Use amount `£0.02` to trigger a generic decline.

**Check in Stripe Dashboard:**
Payments → find the payment → **Decline code** shown in red.

---

### ❌ "Payment processing... spinner never completes"

**What happens:** POS shows "waitingCapture" but never moves forward

**Cause A — Reader disconnected mid-payment**

- Check browser console: `[OrbitStripe] Reader disconnected unexpectedly`
- Fix: Cancel the payment, reconnect reader, try again

**Cause B — Network timeout**

- Fix: Check internet connection on the POS device
- Check Odoo server is accessible

**Cause C — Stripe API timeout**

- Fix: Cancel and retry
- Check Stripe status: https://status.stripe.com

---

### ❌ "Tap card / Apple Pay / Google Pay — nothing happens"

**In test mode:**

- The simulated reader processes automatically — you don't need to physically tap
- If stuck, cancel and retry

**In live mode:**

- Make sure the customer taps within the reader's NFC zone (usually marked with wave symbol)
- Apple Pay: customer double-clicks side button then holds iPhone near reader
- Google Pay: customer unlocks Android phone then holds near reader
- Samsung Pay: swipe up from bottom then tap phone to reader

---

### ❌ "Refund — No Transaction ID"

**What the cashier sees:** Error on refund — "Cannot refund: no Stripe PaymentIntent ID"

**Cause:** The original payment line doesn't have the PI stored (payment wasn't made through Stripe Terminal, or was made before this module was installed)

**Fix:**

1. Find the original PaymentIntent ID from the Stripe Dashboard
2. Go to **Stripe Terminal Payments** backend → open the record
3. Click **💸 Issue Refund** from there instead

---

### ❌ "Refund failed"

**What the cashier sees:** Error popup — "Refund Failed: ..."

**Common reasons:**
| Error | Cause | Fix |
|-------|-------|-----|
| `charge_already_refunded` | Already fully refunded | Check refund status in Stripe Dashboard |
| `invalid_refund_amount` | Amount > original | Reduce refund amount |
| `charge_expired_for_refund` | More than 180 days ago | Must contact Stripe support |
| `insufficient_funds` | Stripe balance too low | Top up Stripe account (rare) |

---

### ❌ "Stripe Terminal SDK failed to load"

**What happens:** POS opens but Stripe SDK doesn't initialise

**Cause:** Browser can't reach `https://js.stripe.com`

**Fix:**

- Check internet connection
- Check firewall/proxy isn't blocking `js.stripe.com`
- Try opening `https://js.stripe.com/terminal/v1/` in a browser tab — should return JS

---

## 3. Common Issues — Technical / Developer

---

### ❌ `card_present with currency usd is not supported in GB`

**Cause:** Odoo company currency is USD, not GBP.

**Fix:**

```
Settings → Companies → [Your Company] → Currency → British Pound (GBP)
```

Then restart Odoo:

```bash
docker exec odoo16_app bash -c "kill -9 \$(ps aux | grep odoo-bin | grep -v grep | awk '{print \$1}')"
docker exec -d odoo16_app python3 /app/odoo-server/odoo-bin -c /app/odoo-server/odoo-server.conf
```

---

### ❌ `column pos_payment_method.orbit_stripe_reader_id does not exist`

**Cause:** Module installed but database column not created yet.

**Fix:**

```bash
# Add column directly
docker exec odoo16_pg14 psql -U odoo -d YOUR_DB_NAME -c "
ALTER TABLE pos_payment_method
ADD COLUMN IF NOT EXISTS orbit_stripe_reader_id VARCHAR;
"

# Then upgrade module
docker exec odoo16_app python3 /app/odoo-server/odoo-bin \
  -c /app/odoo-server/odoo-server.conf \
  -d YOUR_DB_NAME \
  -u orbit_stripe_contactless_payment \
  --stop-after-init
```

---

### ❌ `Test Mode is ON but you entered a Live key (sk_live_...)`

**Cause:** Key type doesn't match mode toggle.

**Fix:**

- Use `sk_test_...` in test mode, OR
- Disable Test Mode in Settings → Stripe Terminal

---

### ❌ `stripe.StripeError: No such reader: tmr_xxx`

**Cause:** Reader ID in Settings doesn't exist in your Stripe account.

**Fix:**

```bash
# List your actual readers
docker exec odoo16_app python3 -c "
import stripe
client = stripe.StripeClient('YOUR_SK_TEST_KEY')
readers = client.v1.terminal.readers.list({'location': 'YOUR_LOCATION_ID'})
for r in readers.data:
    print(r.id, r.label, r.status)
"
```

Copy the correct `tmr_...` ID → paste into Settings → Stripe Terminal → Reader ID.

---

### ❌ POS dropdown doesn't show "Stripe Terminal (Orbit)"

**Cause A:** Journal type is Cash (not Bank)

- Fix: Create a Bank journal with GBP currency and use that

**Cause B:** Module not fully loaded

- Fix:

```bash
docker exec odoo16_app python3 /app/odoo-server/odoo-bin \
  -c /app/odoo-server/odoo-server.conf \
  -d YOUR_DB_NAME \
  -u orbit_stripe_contactless_payment \
  --stop-after-init
```

Then hard refresh browser: `Ctrl+Shift+R`

---

### ❌ `RPC_ERROR: Odoo Server Error ... CacheMiss`

**Cause:** A new field exists in Python but not in the database.

**Fix:**

```bash
# Check which column is missing from the error traceback
# Then add it:
docker exec odoo16_pg14 psql -U odoo -d YOUR_DB_NAME -c "
ALTER TABLE TABLE_NAME ADD COLUMN IF NOT EXISTS COLUMN_NAME DATA_TYPE;
"
# Then upgrade module and restart Odoo
```

---

### ❌ Webhook events not reaching Odoo

**Diagnosis:**

```bash
# Check Stripe CLI is forwarding
stripe listen --forward-to http://localhost:8069/stripe/terminal/webhook

# Check Odoo received it
docker logs odoo16_app 2>&1 | grep -i webhook | tail -10
```

**Common causes:**
| Cause | Fix |
|-------|-----|
| No webhook secret configured | Settings → Stripe Terminal → Webhook Secret |
| Wrong endpoint URL | Must be exactly `/stripe/terminal/webhook` |
| Odoo not accessible from internet | Use Stripe CLI for local testing |
| Wrong signing secret | Re-copy `whsec_...` from Stripe Dashboard |

---

### ❌ `stripe` Python package not installed

**Fix:**

```bash
docker exec odoo16_app pip install stripe
# Or add to requirements.txt and rebuild
```

---

## 4. Common Issues — Refunds

---

### ❌ Refund processed in Stripe but Odoo not updated

**Cause:** `charge.refunded` webhook not configured.

**Fix:**

1. Stripe Dashboard → Developers → Webhooks → your endpoint → Edit
2. Add event: `charge.refunded`
3. Or for local testing: `stripe listen --forward-to localhost:8069/stripe/terminal/webhook`

**Manual fix (without webhook):**

1. Open the payment record in Odoo backend
2. Change state manually (developer mode)
3. Or run:

```bash
docker exec odoo16_pg14 psql -U odoo -d YOUR_DB_NAME -c "
UPDATE stripe_terminal_payment
SET state = 'refunded', stripe_refund_id = 're_...', refund_amount = X.XX
WHERE stripe_payment_intent_id = 'pi_...';
"
```

---

### ❌ `charge_already_refunded`

**Cause:** Full refund already issued — can't refund again.

**Fix:** Check in Stripe Dashboard → the charge shows Refunded badge.
Nothing more to do — customer already received their money.

---

### ❌ `invalid_refund_amount` (amount_too_large)

**Cause:** Refund amount > original payment amount.

**Fix:** Check the **Refunded Amount** field on the payment record.
Max refund = Original Amount − Already Refunded.

---

## 5. Debug Checklist

Run through this when something isn't working:

### Payment not processing:

```
[ ] Is Odoo running?  → docker ps
[ ] Is test mode correct?  → Settings → Stripe Terminal → Test Mode toggle
[ ] Is the correct key type used?  → sk_test_... for test, sk_live_... for live
[ ] Is the Reader ID correct?  → List readers (see Section 3)
[ ] Is company currency GBP?  → Settings → Companies → Currency
[ ] Is the POS journal type Bank with GBP?
[ ] Are there errors in browser console?  → F12 → Console → [OrbitStripe]
[ ] Are there errors in Odoo server log?  → docker logs odoo16_app | grep -i stripe
[ ] Are there errors in Stripe Dashboard?  → Developers → Logs
[ ] Is Stripe API reachable?  → curl https://api.stripe.com
```

### Refund not working:

```
[ ] Is payment status "Succeeded" or "Partially Refunded"?
[ ] Is the refund amount ≤ (original − already refunded)?
[ ] Does the POS line have a transaction_id?  → browser console
[ ] Is the PaymentIntent ID correct?  → check Stripe Dashboard
[ ] Is it within 180 days of the original payment?
[ ] Check Stripe Dashboard → Payments → the charge → any error?
```

### Module not loading:

```
[ ] Is orbit_stripe_contactless_payment listed in Apps as Installed?
[ ] Run: docker exec odoo16_app python3 odoo-bin -u orbit_stripe_contactless_payment --stop-after-init
[ ] Check for Python syntax errors: python3 -m py_compile models/pos_payment_method.py
[ ] Check for view XML errors in Odoo upgrade log
[ ] Hard refresh browser: Ctrl+Shift+R
```

---

## 6. Understanding Error Codes

### Stripe Decline Codes

| Code                 | Meaning                   | Cashier Action                   |
| -------------------- | ------------------------- | -------------------------------- |
| `insufficient_funds` | Card has no money         | Ask for different card           |
| `expired_card`       | Card expired              | Ask for different card           |
| `card_not_supported` | Card type not accepted    | Try a different card             |
| `incorrect_pin`      | Wrong PIN entered         | Ask customer to retry            |
| `lost_card`          | Card reported lost        | Do not accept — contact security |
| `stolen_card`        | Card reported stolen      | Do not accept — contact security |
| `do_not_honor`       | Bank blocked              | Customer calls their bank        |
| `pickup_card`        | Bank says retain card     | Do not accept                    |
| `fraudulent`         | Flagged as fraud          | Do not accept                    |
| `generic_decline`    | Bank declined (no reason) | Ask for different card           |

### Stripe Terminal Error Codes

| Code                       | Meaning                           | Fix                    |
| -------------------------- | --------------------------------- | ---------------------- |
| `reader_busy`              | Reader processing another payment | Wait and retry         |
| `reader_offline`           | Reader lost connection            | Restart reader         |
| `command_not_allowed`      | Wrong action for reader state     | Cancel and restart     |
| `card_swipe_not_available` | Swipe not supported               | Tap or insert card     |
| `interac_unsupported`      | Interac not configured            | Use different payment  |
| `reboot_reader`            | Reader needs restart              | Power cycle the reader |

### HTTP Status Codes (in Stripe Dashboard logs)

| Code  | Meaning                                    |
| ----- | ------------------------------------------ |
| `200` | ✅ Success                                 |
| `400` | ❌ Bad request — check parameters          |
| `401` | ❌ Wrong API key                           |
| `402` | ❌ Card declined                           |
| `403` | ❌ Permission denied                       |
| `404` | ❌ Resource not found (wrong PI/reader ID) |
| `429` | ❌ Rate limit — too many requests          |
| `500` | ❌ Stripe server error — retry             |

---

## Quick Reference — Log Locations

| Log                    | Location                                    | Command                                           |
| ---------------------- | ------------------------------------------- | ------------------------------------------------- |
| Odoo backend records   | Point of Sale → Stripe Terminal Payments    | Click any record                                  |
| Stripe payments        | dashboard.stripe.com/test/payments          | Filter by date/amount                             |
| Stripe API calls       | dashboard.stripe.com/test/logs              | Filter by endpoint                                |
| Stripe events/webhooks | dashboard.stripe.com/test/events            | Filter by event type                              |
| Browser POS logs       | F12 → Console                               | Filter: `[OrbitStripe]`                           |
| Odoo server log (live) | Docker container                            | `docker logs odoo16_app -f \| grep stripe`        |
| Odoo server log (file) | `/app/odoo-server/log/odoo/odoo-server.log` | `tail -f \| grep stripe`                          |
| Database records       | PostgreSQL                                  | `psql -c "SELECT * FROM stripe_terminal_payment"` |
| Webhook delivery       | Stripe CLI or Dashboard → Events            | `stripe listen --forward-to ...`                  |
