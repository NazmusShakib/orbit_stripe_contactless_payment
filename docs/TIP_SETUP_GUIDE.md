# Stripe Terminal — Tip / Gratuity Setup Guide

Complete guide for enabling and using tip/gratuity support with Stripe Terminal in Odoo 16 POS.

---

## Overview

The tip feature shows a **tip selection popup** in the POS before the customer taps their card.
The cashier presents the screen to the customer who selects:

- **No Tip** — skip gratuity
- **10% / 15% / 20%** (or your configured percentages) — preset buttons showing £ amounts
- **Custom** — enter any amount

After selection, Stripe captures the **base order amount + tip** in a single card tap.

### How it works technically

```
Cashier clicks "Send"
       ↓
Tip popup shown (customer selects 15% = £3.75 on a £25 order)
       ↓
Payment line updated: £25.00 + £3.75 = £28.75
       ↓
Stripe PaymentIntent created: £25.00 (base amount)
       ↓
Customer taps card / Apple Pay / Google Pay
       ↓
Stripe capture called: £28.75 (base + tip)
    [Stripe allows up to +20% overage for tips]
       ↓
Card charged: £28.75
```

> **Stripe tip overpayment**: Stripe Terminal allows capturing up to **20% more** than the
> authorised PaymentIntent amount specifically to accommodate tips. This is supported for
> GBP on UK Stripe accounts.
>
> Stripe docs: https://stripe.com/docs/terminal/features/collecting-tips

---

## Step 1 — Enable Tip in Settings

1. Go to **Settings → Stripe Terminal**
2. Toggle **"Enable Tip / Gratuity"** → ON
3. Set **Tip Percentages**: e.g. `10,15,20` (comma-separated, no spaces)
   - Common options: `10,15,20` | `15,18,20` | `10,15,20,25`
4. Click **Save**

---

## Step 2 — Verify POS Config Loaded

1. Close any open POS sessions
2. Reopen POS → **hard refresh browser** (`Ctrl+Shift+R`)
3. The tip config is loaded into POS at session start from `pos_session._get_pos_ui_pos_config()`

---

## Step 3 — Taking a Payment with Tip

1. Add products to order
2. Click **Payment**
3. Select **Card / Contactless**
4. Click **Send / Validate**
5. **Tip popup appears:**

```
┌─────────────────────────────────────┐
│  💰 Add a Tip / Gratuity            │
│                                     │
│  Order Total:          £25.00       │
│                                     │
│  ┌─────────┐  ┌────────────────┐    │
│  │ No Tip  │  │    10%  £2.50  │    │
│  └─────────┘  └────────────────┘    │
│  ┌────────────────┐  ┌──────────┐   │
│  │  15%   £3.75   │  │  20%     │   │
│  │                │  │  £5.00   │   │
│  └────────────────┘  └──────────┘   │
│  ┌──────────────────────────────┐   │
│  │   Custom — Enter amount      │   │
│  └──────────────────────────────┘   │
│                                     │
│  Tip:              £3.75            │
│  Total to charge:  £28.75           │
│                                     │
│  [No Tip – Skip] [✓ Confirm & Pay]  │
└─────────────────────────────────────┘
```

6. Customer selects tip (or cashier presents screen to customer)
7. Click **Confirm & Pay** → customer taps card
8. Stripe charges **£28.75** (base + tip) in one tap

---

## Step 4 — Verify in Stripe Dashboard

After a tipped payment:

1. Go to https://dashboard.stripe.com/test/payments
2. Find the payment → amount shows **£28.75**
3. Click it → under **Payment details**:
   - Amount authorised: £25.00
   - Amount captured: £28.75
   - Difference: £3.75 (tip)

---

## Configuration Reference

| Setting         | Location                   | Default    | Description            |
| --------------- | -------------------------- | ---------- | ---------------------- |
| Enable Tip      | Settings → Stripe Terminal | OFF        | Shows tip popup in POS |
| Tip Percentages | Settings → Stripe Terminal | `10,15,20` | Preset % buttons       |

### ir.config_parameter keys

| Key                                                | Value             |
| -------------------------------------------------- | ----------------- |
| `orbit_stripe_contactless_payment.tip_enabled`     | `True` or `False` |
| `orbit_stripe_contactless_payment.tip_percentages` | `10,15,20`        |

### POS config values (injected into frontend)

| Key                            | Type    | Description                 |
| ------------------------------ | ------- | --------------------------- |
| `orbit_stripe_tip_enabled`     | boolean | Whether tip popup shows     |
| `orbit_stripe_tip_percentages` | string  | Comma-separated percentages |

---

## Tip Examples

| Order  | Tip %      | Tip £  | Total  |
| ------ | ---------- | ------ | ------ |
| £10.00 | 10%        | £1.00  | £11.00 |
| £10.00 | 15%        | £1.50  | £11.50 |
| £10.00 | 20%        | £2.00  | £12.00 |
| £25.00 | 10%        | £2.50  | £27.50 |
| £25.00 | 15%        | £3.75  | £28.75 |
| £25.00 | 20%        | £5.00  | £30.00 |
| £50.00 | 15%        | £7.50  | £57.50 |
| £50.00 | Custom £10 | £10.00 | £60.00 |

---

## Stripe Tip Overpayment Limits

Stripe Terminal allows capturing **more than the original authorised amount** for tips:

| Currency | Max Overage                |
| -------- | -------------------------- |
| GBP (UK) | +20% of original           |
| USD (US) | +20% of original           |
| EUR      | +20% of original           |
| AUD      | +20% of original           |
| CAD      | +20% of original           |
| Other    | Varies — check Stripe docs |

**Example**: PI authorised for £25.00 → max capture = £30.00 (£25 × 1.20)

If tip exceeds 20%, Stripe will return an error. In that case:

- Reduce the tip amount
- Or create a new PaymentIntent for the full amount including tip

---

## Disabling Tips Per-Order

If a customer doesn't want to be shown the tip prompt:

1. Cashier can click **"No Tip – Skip"** immediately
2. Payment proceeds for the base amount only

To **permanently disable** for all orders:

- Settings → Stripe Terminal → Enable Tip → OFF

---

## Reporting Tips in Odoo

Tips added via Stripe Terminal are captured as part of the payment amount.
The POS order total will reflect the full charged amount (base + tip).

To track tips separately:

1. Enable Odoo's built-in tip product: **POS Settings → Payment → Tip Product**
2. The tip amount can be posted to a separate "Tips" account in your chart of accounts

---

## Console Log (During Tipped Payment)

Watch F12 → Console → filter `[OrbitStripe]`:

```
[OrbitStripe] Showing tip popup (order total: £25.00)
[OrbitStripe] Tip selected: £3.75 | Total: £28.75
[OrbitStripe] Stripe will capture £28.75 (base + tip)
[OrbitStripe] Step 1: PaymentIntent created
[OrbitStripe] ← PaymentIntent {"id":"pi_3T...", "amount":"£25", "currency":"gbp"}
[OrbitStripe] Step 2: Card tapped
[OrbitStripe] Step 3: processPayment
[OrbitStripe] Step 4: Capturing with tip: £28.75 (base + £3.75 tip)
[OrbitStripe] Capture SUCCESS. Status: succeeded
[OrbitStripe] ━━━ PAYMENT COMPLETE ━━━
[OrbitStripe] Transaction: pi_3T... | Card: visa
```

Also visible in **Stripe Log** panel (click the button in POS top bar).

---

## Troubleshooting

### Tip popup not appearing

- Check **Settings → Stripe Terminal → Enable Tip** is ON
- Hard refresh browser after saving settings: `Ctrl+Shift+R`
- Check POS config loaded tip: Open browser console → `this.env.pos.config.orbit_stripe_tip_enabled`

### `amount_too_large` error on capture

- The tip amount exceeds Stripe's 20% overage limit
- Reduce the custom tip amount
- Example: £25 order → max tip = £5.00 (20%)

### Tip shown but not charged

- Check browser console for `[OrbitStripe] ⚡ Step 4: Capturing with tip`
- If missing, `line._tipAmount` may not be set — ensure module is upgraded

### Custom tip not accepted

- Input must be a valid number (e.g. `3.50` not `£3.50`)
- Must be > 0 and ≤ 20% of order total for Stripe overpayment

---

## For New Projects — Quick Setup

1. **Install module** (see [INSTALLATION_GUIDE.md](INSTALLATION_GUIDE.md))
2. **Settings → Stripe Terminal:**
   - Add API keys
   - Add Location ID + Reader ID
   - Set company currency = GBP
   - Enable Tip → ON
   - Set percentages: `10,15,20`
3. **POS → Payment Methods → New:**
   - Journal: Bank (GBP)
   - Terminal: Stripe Terminal (Orbit)
4. **POS → Configuration → add payment method**
5. **Open POS → take a payment → tip popup appears**
