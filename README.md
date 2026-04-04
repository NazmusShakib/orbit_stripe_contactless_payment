# Stripe Terminal Payment — Odoo Module

> **Phase 1: Developer / Test / Simulation Mode**  
> No real hardware required. Uses Stripe's test environment and simulated readers.

---

## Module Overview

This module integrates **Stripe Terminal** for contactless in-person card payments directly inside Odoo 16.

It provides:

- Admin settings for Stripe API credentials
- PaymentIntent creation via Stripe API
- Simulated card-present payment collection
- Payment confirmation and status tracking
- Full audit log with chatter history in Odoo
- A setup wizard to create simulated readers without leaving Odoo

---

## Folder Structure

```
orbit_stripe_contactless_payment/
├── __init__.py
├── __manifest__.py
│
├── models/
│   ├── __init__.py
│   ├── stripe_terminal_payment.py     # Core payment record model
│   ├── res_config_settings.py         # Settings panel fields + wizard launcher
│   ├── stripe_setup_wizard.py         # Transient wizard: test connection + create reader
│   └── ...
│
├── services/
│   ├── __init__.py
│   └── stripe_terminal_service.py     # All Stripe API calls (Stripe v15 client API)
│
├── controllers/
│   ├── __init__.py
│   └── main.py                        # HTTP routes: connection token + webhook placeholder
│
├── views/
│   ├── stripe_terminal_payment_views.xml   # Form, list, search views
│   ├── stripe_setup_wizard_views.xml       # Setup & Test wizard UI
│   ├── res_config_settings_views.xml       # Settings panel section
│   ├── menus.xml                           # Top-level menus
│   └── ...
│
├── security/
│   ├── groups.xml                     # Two groups: User and Manager
│   └── ir.model.access.csv            # Model access rights
│
├── data/
│   └── ir_config_parameter_data.xml  # Default system params + sequence
│
├── demo/
│   └── demo_data.xml                 # Sample records (succeeded, failed, draft)
│
└── static/
    ├── description/index.html
    └── src/
        ├── js/stripe_terminal_widget.js    # Phase 2 JS SDK stub
        └── css/stripe_terminal.css         # UI styles
```

---

## Installation

### 1. Prerequisites

**Install the `stripe` Python package inside Docker:**

```bash
docker exec -it odoo16_app pip3 install stripe

# Verify
docker exec -it odoo16_app python3 -c "import stripe; print(stripe._version.VERSION)"
```

**No changes needed to `docker-compose.yml` or `odoo-server.conf`.**  
The `custom/addons` path is already configured.

### 2. Install the Module

```bash
# Option A: via command line (recommended first time)
docker exec odoo16_app bash -c "
  cd /app/odoo-server &&
  python3 odoo-bin --config=odoo-server.conf \
    -d odoo_16 -i orbit_stripe_contactless_payment --stop-after-init
"

# Option B: via Odoo UI
# Settings → Activate Developer Mode → Apps → Update Apps List
# Search "Orbit Stripe Terminal" → Install
```

### 3. Start Odoo

```bash
docker exec -d odoo16_app bash -c "
  cd /app/odoo-server &&
  python3 odoo-bin --config=odoo-server.conf --dev=all
"
```

### 4. Upgrade after code changes

```bash
docker exec odoo16_app bash -c "
  pkill -f odoo-bin; sleep 2
  cd /app/odoo-server &&
  python3 odoo-bin --config=odoo-server.conf \
    -d odoo_16 -u orbit_stripe_contactless_payment --stop-after-init
"
```

---

## Access Control

| Group                         | Access                                |
| ----------------------------- | ------------------------------------- |
| **Stripe Terminal / User**    | Create & process payments             |
| **Stripe Terminal / Manager** | Full access + Settings + Setup Wizard |

**To add a user via UI:**  
Settings → Users & Companies → Groups → search "Stripe Terminal / Manager" → add user → Save

**To add a user via shell (quick fix):**

```bash
docker exec odoo16_app bash -c "
cd /app/odoo-server
python3 odoo-bin shell --config=odoo-server.conf -d odoo_16 --no-http 2>/dev/null <<'EOF'
grp = env.ref('orbit_stripe_contactless_payment.group_stripe_terminal_manager')
user = env['res.users'].search([('login', '=', 'your_login_here')], limit=1)
grp.sudo().write({'users': [(4, user.id)]})
env.cr.commit()
print('Done:', user.name, 'added to Stripe Terminal Manager')
EOF
"
```

---

## Configuration

### Step 1 — Get Stripe Test Credentials

1. Log in to **https://dashboard.stripe.com**
2. Switch to **Test Mode** (toggle in top-left)
3. Go to **Developers → API Keys**
4. Copy:
   - **Secret key**: `sk_test_...`
   - **Publishable key**: `pk_test_...`

### Step 2 — Create a Terminal Location

1. In Stripe Dashboard → **Terminal → Locations**
2. Click **+ New location** → fill in any address → Save
3. Copy the **Location ID**: `tml_...`

### Step 3 — Configure in Odoo

1. Open Odoo → **Settings → General Settings**
2. Scroll down to **"Stripe Terminal"** section
3. Fill in:

| Field                  | Value                                 |
| ---------------------- | ------------------------------------- |
| Stripe Secret Key      | `sk_test_...`                         |
| Stripe Publishable Key | `pk_test_...`                         |
| Terminal Location ID   | `tml_...`                             |
| Reader ID              | (leave blank — wizard will create it) |
| Test Mode              | ON                                    |

4. Click **Save**

### Step 4 — Create a Simulated Reader

1. In Settings → Stripe Terminal → click **Open Setup & Test Wizard**
2. Click **Test Stripe Connection** → verify it shows SUCCESSFUL
3. Click **Create Simulated Reader** → the Reader ID (`tmr_...`) is auto-saved to Settings
4. Click **Close**

---

## Payment Flow (Phase 1 — Simulated)
```
┌──────────────────────────────────────────────────────────────────────────────┐
│                         STRIPE TERMINAL PAYMENT FLOW                         │
│                            (Phase 1 — Simulated)                             │
└──────────────────────────────────────────────────────────────────────────────┘

┌───────────────┬──────────────────────────────────────────┬───────────────────┐
│ User Action   │ Odoo Process                             │ Stripe API        │
├───────────────┼──────────────────────────────────────────┼───────────────────┤
│ 1. New Payment│ User enters payment amount.              │                   │
│               │ Odoo creates a `stripe.terminal.payment` │                   │
│               │ record.                                  │                   │
│               │ State: `Draft`                           │                   │
├───────────────┼──────────────────────────────────────────┼───────────────────┤
│ 2. Create     │ Odoo calls `stripe.PaymentIntent.create()`                   │
│ Payment Intent│ with `payment_method_types=['card_present']`.                │
│               │ Stripe returns a PaymentIntent ID (`pi_...`)                 │
│               │ and `client_secret`.                                         │
│               │ Odoo stores these values in the payment record.              │
│               │ State: `Intent Created`                                      │
├───────────────┼──────────────────────────────────────────┼───────────────────┤
│ 3. Simulate   │ Odoo triggers `process_payment_intent()` │ Reader processes  │
│ Card Tap      │ followed by `present_payment_method()`.  │ payment intent.   │
│               │ A test helper simulates the customer     │ Stripe simulates  │
│               │ tapping their card.                      │ a card-present    │
│               │ State: `Processing`                      │ transaction.      │
├───────────────┼──────────────────────────────────────────┼───────────────────┤
│ 4. Confirm    │ Odoo calls `PaymentIntent.retrieve()`    │ Stripe returns    │
│ Payment       │ with `expand=['latest_charge']`.         │ final payment     │
│               │ Odoo stores the Charge ID (`ch_...`).    │ status and charge │
│               │ State: `Succeeded`                       │ reference.        │
└───────────────┴──────────────────────────────────────────┴───────────────────┘

Additional Notes:
- All steps are logged in the record’s Chatter (`message_ids`).
- All Stripe references such as `pi_...` and `ch_...` are stored in the Odoo record.
```

### State Machine

```
  Draft
    │
    ▼ [Create Payment Intent]
  Intent Created
    │
    ▼ [Simulate Card Tap]
  Processing
    │
    ▼ [Confirm Payment]
  Succeeded or Failed

  Any non-succeeded state can be → Cancelled
  Failed / Cancelled can be → Reset to Draft (for retry)
```

---

## Step-by-Step Test

### In Odoo UI:

1. Go to **Stripe Terminal** (top menu) → **New Payment**
2. Fill in:
   - **Description**: `Test Payment - Table 5`
   - **Amount**: `25.00`
   - **Currency**: `USD`
3. Click **1. Create Payment Intent**
   - Record shows: `stripe_payment_intent_id = pi_xxxxx`
   - State → **Intent Created**
4. Click **2. Simulate Card Tap**
   - State → **Processing**
   - Chatter: "Payment simulation initiated"
5. Click **3. Confirm Payment**
   - State → **Succeeded** (green banner)
   - `stripe_charge_id = ch_xxxxx` visible on record

### Verify in Stripe Dashboard:

- Go to **https://dashboard.stripe.com/test/payments**
- Your `pi_xxxxx` payment appears with status **Succeeded**
- Click it to see full charge details, card details, and metadata

---

## 🌐 HTTP Endpoints

| URL                                 | Method | Auth         | Purpose                                       |
| ----------------------------------- | ------ | ------------ | --------------------------------------------- |
| `/stripe/terminal/connection_token` | POST   | user session | Returns Terminal JS SDK connection token      |
| `/stripe/terminal/webhook`          | POST   | none         | Stripe webhook receiver (Phase 2 placeholder) |
| `/stripe/terminal/readers`          | POST   | user session | Lists available readers                       |

---

## Stripe Python Package Compatibility

| stripe version | Compatibility                                   |
| -------------- | ----------------------------------------------- |
| v2 – v7        | Old-style API (`stripe.PaymentIntent.create()`) |
| v8 – v10       | Old-style still works with deprecation warnings |
| **v11 – v15**  | **This module uses `StripeClient` (new API)**   |

This module uses `stripe.StripeClient` (introduced in v11) for all API calls — fully compatible with the installed v15.

---

## Known Limitations (Phase 1)

| Limitation            | Phase 2 Fix                                                  |
| --------------------- | ------------------------------------------------------------ |
| No real hardware      | Replace `simulate_reader_payment()` with real reader flow    |
| Webhooks are log-only | Implement signature verification in `controllers/main.py`    |
| No accounting entries | Add `account.payment` creation after payment succeeds        |
| No POS integration    | Link `stripe.terminal.payment` to `pos.order`                |
| Manual 3-step flow    | Automate via webhooks + reader event callbacks               |
| JS SDK not loaded     | Load `https://js.stripe.com/terminal/v1/` + implement widget |
| No refund support     | Add `stripe.Refund.create()` action                          |

---

## Phase 2 — Real Hardware Checklist

When you're ready to connect a real Stripe Terminal reader (e.g. BBPOS WisePOS E, Stripe Reader S700):

- [ ] Replace `registration_code: 'simulated-wpe'` with real device registration code
- [ ] Implement webhook signature verification (`whsec_...`) in `controllers/main.py`
- [ ] Load Stripe Terminal JS SDK in `stripe_terminal_widget.js`
- [ ] Implement `fetchConnectionToken` → `/stripe/terminal/connection_token`
- [ ] Implement `collectPaymentMethod` + `processPayment` in JS
- [ ] Add `account.payment` journal entry creation after payment succeeds
- [ ] Add `pos.order` linkage for POS use
- [ ] Add refund flow via `stripe.Refund`
- [ ] Move `sk_live_...` key into Odoo vault / environment variable (not Settings UI)
- [ ] Set up Stripe webhook endpoint in Stripe Dashboard pointing to `/stripe/terminal/webhook`

---

## Useful Commands

```bash
# Install stripe package
docker exec -it odoo16_app pip3 install stripe

# Install module (first time)
docker exec odoo16_app bash -c "cd /app/odoo-server && python3 odoo-bin --config=odoo-server.conf -d odoo_16 -i orbit_stripe_contactless_payment --stop-after-init"

# Upgrade module (after code changes)
docker exec odoo16_app bash -c "pkill -f odoo-bin; sleep 2; cd /app/odoo-server && python3 odoo-bin --config=odoo-server.conf -d odoo_16 -u orbit_stripe_contactless_payment --stop-after-init"

# Start Odoo
docker exec -d odoo16_app bash -c "cd /app/odoo-server && python3 odoo-bin --config=odoo-server.conf --dev=all"

# Tail Odoo log
docker exec odoo16_app tail -f /var/log/odoo.log

# Open Odoo shell
docker exec -it odoo16_app bash -c "cd /app/odoo-server && python3 odoo-bin shell --config=odoo-server.conf -d odoo_16 --no-http"
```

---

## References

- [Stripe Terminal Docs](https://stripe.com/docs/terminal)
- [Stripe Python SDK v15](https://github.com/stripe/stripe-python)
- [Stripe Terminal Test Cards](https://stripe.com/docs/terminal/references/testing)
- [Stripe Dashboard (Test Mode)](https://dashboard.stripe.com/test)
- [Odoo 16 ORM Reference](https://www.odoo.com/documentation/16.0/developer/reference/backend/orm.html)

---

## Author

**Orbit Media**  
Module: `orbit_stripe_contactless_payment`  
Version: `16.0.1.0.0`  
License: LGPL-3
