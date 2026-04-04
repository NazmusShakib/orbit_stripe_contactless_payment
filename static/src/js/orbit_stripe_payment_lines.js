/* ===========================================================================
   Orbit Stripe Terminal — PaymentScreenPaymentLines extension
   ===========================================================================
   Extends PaymentScreenPaymentLines to handle the "Confirm Payment" button
   click event ('orbit-stripe-confirm') that appears in the POS payment screen
   when a Stripe Terminal payment is in 'waitingCapture' status.

   When the cashier clicks "Confirm Payment":
     - We find the OrbitStripePayment terminal instance on the payment line
     - Call terminal.confirmPayment() which resolves the internal gate Promise
     - The awaiting send_payment_request() then proceeds to capture → done
   =========================================================================== */

odoo.define('orbit_stripe_contactless_payment.PaymentLinesExtension', function (require) {
    'use strict';

    const PaymentScreenPaymentLines = require('point_of_sale.PaymentScreenPaymentLines');
    const Registries                = require('point_of_sale.Registries');

    const OrbitStripePaymentLines = (PaymentScreenPaymentLines) =>
        class extends PaymentScreenPaymentLines {

            /**
             * Handle the "Confirm Payment" button click for Stripe Terminal.
             * Triggered by t-on-click in OrbitStripePaymentLines.xml.
             *
             * @param {Object} line  The POS paymentline object
             */
            onOrbitStripeConfirm(line) {
                if (!line || line.payment_status !== 'waitingCapture') {
                    return;
                }

                const terminal = line.payment_method && line.payment_method.payment_terminal;
                if (!terminal || typeof terminal.confirmPayment !== 'function') {
                    console.error('[OrbitStripe] No terminal.confirmPayment found on payment line.');
                    return;
                }

                terminal.confirmPayment();
            }

        };

    Registries.Component.extend(PaymentScreenPaymentLines, OrbitStripePaymentLines);

    return OrbitStripePaymentLines;
});
