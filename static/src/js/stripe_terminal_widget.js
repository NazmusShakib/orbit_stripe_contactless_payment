/** @odoo-module **/
/**
 * stripe_terminal_widget.js
 * ==========================
 * Frontend JavaScript for Stripe Terminal backend widget.
 *
 * Phase 1: Minimal JS — the main payment flow is handled server-side
 * via Odoo form view buttons and Python actions.
 *
 * Phase 2 note: Replace this file with a full Stripe Terminal JS SDK
 * integration when real hardware readers are used.
 *
 * Phase 2 implementation will include:
 *   1. Load Stripe Terminal SDK:
 *        <script src="https://js.stripe.com/terminal/v1/"></script>
 *   2. Initialise terminal:
 *        const terminal = StripeTerminal.create({
 *            onFetchConnectionToken: fetchConnectionToken,
 *            onUnexpectedReaderDisconnect: handleDisconnect,
 *        });
 *   3. Discover readers
 *   4. Connect to reader
 *   5. collectPaymentMethod(clientSecret)
 *   6. processPayment(paymentMethod)
 *   7. Call Odoo backend to confirm and record result
 *
 * Connection token endpoint (already implemented in Phase 1):
 *   POST /stripe/terminal/connection_token
 */

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component } from "@odoo/owl";

/**
 * StripeTerminalStatusWidget
 * --------------------------
 * A simple display widget that shows the payment state with a coloured badge.
 * Registered as a field widget so it can be used in form/list views.
 *
 * Phase 1: Display only.
 * Phase 2: Add reader connection status, real-time updates via websocket/polling.
 */
class StripeTerminalStatusWidget extends Component {
    static template = "orbit_stripe_contactless_payment.StatusBadge";

    setup() {
        this.notification = useService("notification");
    }

    /**
     * Show a friendly notification when the payment state changes.
     * Called from the form view's on_change or after button actions.
     *
     * Phase 2: Hook into real reader events here.
     */
    showStatusNotification(state) {
        const messages = {
            succeeded: { message: "✅ Payment succeeded!", type: "success" },
            failed:    { message: "❌ Payment failed. See error details.", type: "danger" },
            processing: { message: "⏳ Reader is processing the payment…", type: "warning" },
            cancelled: { message: "🚫 Payment cancelled.", type: "info" },
        };
        const notif = messages[state];
        if (notif) {
            this.notification.add(notif.message, { type: notif.type, sticky: false });
        }
    }
}

// ── Phase 2: Stripe Terminal JS SDK helper functions (stubs) ─────────────────
// Uncomment and implement these when integrating real Stripe Terminal hardware.

/**
 * Fetch a connection token from the Odoo backend.
 * Called by the Stripe Terminal SDK during initialisation.
 *
 * @returns {Promise<string>} The connection token secret.
 *
async function fetchConnectionToken() {
    const result = await fetch('/stripe/terminal/connection_token', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': odoo.csrf_token,
        },
        body: JSON.stringify({ jsonrpc: '2.0', method: 'call', params: {} }),
    });
    const data = await result.json();
    if (data.result && data.result.secret) {
        return data.result.secret;
    }
    throw new Error('Failed to fetch Stripe Terminal connection token.');
}
*/

/**
 * Handle unexpected reader disconnection.
 *
async function handleUnexpectedDisconnect() {
    console.warn('[Stripe Terminal] Reader unexpectedly disconnected.');
    // Phase 2: Show error notification, attempt reconnection, etc.
}
*/

/**
 * Full Phase 2 payment flow (pseudocode):
 *
async function runTerminalPayment(clientSecret) {
    // 1. Collect payment method from the physical reader
    const collectResult = await terminal.collectPaymentMethod(clientSecret);
    if (collectResult.error) {
        console.error('collectPaymentMethod error:', collectResult.error);
        return;
    }

    // 2. Process the payment
    const processResult = await terminal.processPayment(collectResult.paymentIntent);
    if (processResult.error) {
        console.error('processPayment error:', processResult.error);
        return;
    }

    // 3. Notify backend to capture and record the payment
    // Call Odoo RPC to action_confirm_payment on the stripe.terminal.payment record
    console.log('Payment processed successfully:', processResult.paymentIntent.id);
}
*/

// Register the widget (Phase 1 — no-op registration for future use)
// registry.category("fields").add("stripe_terminal_status", StripeTerminalStatusWidget);

console.log("[Orbit Stripe Terminal] Phase 1 JS loaded. Real SDK integration ready for Phase 2.");
