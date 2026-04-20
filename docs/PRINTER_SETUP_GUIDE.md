# Stripe Terminal Printer Setup Guide

This guide covers the current receipt printing flow for `orbit_stripe_contactless_payment`.

As of the current module version:

- `Receipt` and `Refund` from `Stripe Terminal Payments` open a thermal HTML receipt page
- printing is handled by the browser print dialog
- this works for both `POS` and `Backend` source payments
- this is not yet a direct IoT / POS-proxy printer push

---

## 1. What This Setup Does

The module prints customer receipts in a thermal receipt layout instead of a full-page PDF.

Recommended use:

- `Receipt` for sale receipts
- `Refund` for refund receipts

Use invoice or credit note documents separately when you need formal accounting documents.

---

## 2. Recommended Setup

Use this setup unless you specifically need silent one-click printing:

- browser: `Google Chrome` or `Microsoft Edge`
- printer type: thermal receipt printer
- paper width: `80mm` preferred, `58mm` supported if your printer uses it
- printing method: browser print dialog

This is the simplest and most stable setup for cashier use.

---

## 3. Before You Start

Make sure:

1. The thermal printer is installed on the cashier machine.
2. The printer appears in the operating system printer list.
3. The correct paper width is configured in the printer driver.
4. Odoo is opened from the same machine that can access the printer.

---

## 4. Printer Driver Setup

Set the printer driver first at operating system level.

### Windows

1. Open `Settings -> Bluetooth & devices -> Printers & scanners`
2. Select the receipt printer
3. Open `Printing preferences`
4. Set paper size to `80mm` or `58mm`
5. Set margins to minimum if the driver supports it
6. Save

### macOS

1. Open `System Settings -> Printers & Scanners`
2. Select the receipt printer
3. Open the printer options or default preset settings
4. Set paper size to `80mm` or `58mm`
5. Save the preset

### Linux

1. Open your printer settings
2. Select the receipt printer
3. Set media or page size to `80mm` or `58mm`
4. Save the default profile

If the driver is still configured for A4 or Letter, the receipt will print badly even if Odoo is correct.

---

## 5. Browser Print Setup

Use Chrome or Edge.

When printing a receipt for the first time:

1. Open the receipt page from Odoo
2. In the browser print dialog, select the thermal printer
3. Set `Paper size` to the printer paper width
4. Set `Margins` to `None` or the smallest option available
5. Set `Scale` to `100%`
6. Turn off browser `Headers and footers`
7. Save the printer preset if your browser or OS supports it

Recommended:

- keep the receipt printer as a saved destination
- keep one preset for `80mm`
- keep another preset for `58mm` if you use different sites or devices

---

## 6. How To Print From Odoo

### Sale Receipt

1. Open `Stripe Terminal Payments`
2. Open the payment record or use the list-view button
3. Click `Receipt`
4. The thermal receipt page opens
5. Print from the browser dialog

### Refund Receipt

1. Open `Stripe Terminal Payments`
2. Open a refunded payment record
3. Click `Refund`
4. The thermal refund receipt page opens
5. Print from the browser dialog

Both flows support:

- `Source Type = POS`
- `Source Type = Backend`

---

## 7. Expected Receipt Behavior

The thermal receipt page is designed for narrow paper and should:

- open as HTML, not as a PDF download
- print in a receipt-style width
- show sale or refund information clearly
- work from standard browser printing

If you still see a full-page print layout, the issue is usually browser or driver settings, not the Odoo template.

---

## 8. Recommended Staff Workflow

For daily cashier use:

1. Click `Receipt` or `Refund`
2. Confirm the thermal printer is selected
3. Print
4. Hand the receipt to the customer

If the browser reverts to another printer, reselect the thermal printer and save the preset again.

---

## 9. Troubleshooting

### The print opens as a full page

Check:

- printer driver paper size is `80mm` or `58mm`
- browser margins are `None`
- browser headers/footers are disabled
- scale is `100%`

### The receipt prints on A4

The operating system or browser is still using a standard paper profile.

Fix:

1. Open printer preferences
2. Change the default paper size to `80mm` or `58mm`
3. Reopen the receipt page
4. Print again

### There is too much blank space

Check:

- driver page length
- browser margins
- auto-cut settings on the printer

### The receipt is too wide or text is cut off

Use the correct paper width:

- `80mm` template on an `80mm` printer is ideal
- a `58mm` printer may need a driver-side scale adjustment

### The browser asks for print confirmation every time

That is expected in the current setup.

The current module uses browser printing, not silent direct printer output.

---

## 10. Important Limitation

This setup is not the same as native POS receipt-printer integration.

Current behavior:

- opens a thermal HTML receipt page
- relies on browser print

Not implemented yet:

- silent printing
- direct IoT Box printer push from the backend menu
- automatic routing to a specific POS printer from backend-origin payments

---

## 11. When To Consider Advanced Printer Integration

You should only move to the advanced setup if you need:

- one-click direct printing without browser dialog
- silent printing at the counter
- forced routing to a configured POS receipt printer

That setup requires additional development because backend Stripe payments do not automatically belong to one POS printer.

---

## 12. Go-Live Checklist

Before using this with staff:

- thermal printer installed
- correct paper width configured
- browser preset saved
- one sale receipt tested
- one refund receipt tested
- cashier knows which printer to select

---

## 13. Related Documents

- [README.md](../README.md)
- [INSTALLATION_GUIDE.md](INSTALLATION_GUIDE.md)
- [README_LIVE_MODE.md](README_LIVE_MODE.md)
- [DEBUG_AND_FAQ.md](DEBUG_AND_FAQ.md)
