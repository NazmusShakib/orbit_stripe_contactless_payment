/* ===========================================================================
   Orbit Stripe Terminal — Register POS Payment Method
   Registers 'orbit_stripe_terminal' so the POS knows which JS class handles it.
   Must match the value returned by _get_payment_terminal_selection() in Python.
   =========================================================================== */
odoo.define('orbit_stripe_contactless_payment.models', function (require) {
    'use strict';

    const models             = require('point_of_sale.models');
    const OrbitStripePayment = require('orbit_stripe_contactless_payment.payment');

    models.register_payment_method('orbit_stripe_terminal', OrbitStripePayment);
});
