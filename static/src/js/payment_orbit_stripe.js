/* global StripeTerminal */
/* ===========================================================================
   Orbit Stripe Terminal — POS Payment Handler
   ===========================================================================

   Works in BOTH Test/Simulation mode and Live/Production mode.

   Payment flow:
     1. init()                 → create StripeTerminal SDK instance
     2. send_payment_request() → create PaymentIntent (GBP, card_present)
                                  → discover + connect reader
                                  → collectPaymentMethod (customer taps)
                                  → processPayment
                                  → capture (server-side)
     3. send_payment_cancel()  → cancel collection + cancel PaymentIntent
     4. close()                → disconnect reader

   Accepted contactless payment methods (UK):
     • Physical cards: Visa, Mastercard, Amex, Maestro
     • Apple Pay (iOS)   — Tap to Pay on iPhone or Stripe Terminal reader
     • Google Pay (Android) — Tap to Pay on Android or Stripe Terminal reader
     • Samsung Pay and other NFC wallets

   Test mode:  discoverReaders({ simulated: true }) finds simulated readers.
   Live mode:  discoverReaders({}) finds real registered readers on the network.
   =========================================================================== */

odoo.define('orbit_stripe_contactless_payment.payment', function (require) {
    'use strict';

    const core             = require('web.core');
    const rpc              = require('web.rpc');
    const PaymentInterface = require('point_of_sale.PaymentInterface');
    const { Gui }          = require('point_of_sale.Gui');

    const _t = core._t;

    const OrbitStripePayment = PaymentInterface.extend({

        // ===================================================================
        // Lifecycle
        // ===================================================================

        init: function (pos, payment_method) {
            this._super(...arguments);
            this.enable_reversals();
            this._terminal      = null;   // StripeTerminal SDK instance
            this._connected     = false;  // whether reader is connected
            this._activeIntent  = null;   // current payment_intent_id being collected
            this._createTerminal();
        },

        // ===================================================================
        // Stripe Terminal SDK initialisation
        // ===================================================================

        _isTestMode: function () {
            return this._parseTestModeValue(
                this.pos.config && this.pos.config.orbit_stripe_test_mode
            );
        },

        _parseTestModeValue: function (value) {
            return ![false, 'False', 'false', 0, '0', null].includes(value);
        },

        _refreshRuntimeConfig: async function () {
            try {
                const data = await rpc.query({
                    model: 'pos.payment.method',
                    method: 'orbit_stripe_runtime_config',
                    kwargs: { context: this.pos.env.session.user_context },
                }, { silent: true });

                if (!data) {
                    return;
                }

                if (this.pos.config) {
                    this.pos.config.orbit_stripe_test_mode =
                        this._parseTestModeValue(data.test_mode);
                    this.pos.config.orbit_stripe_reader_id = data.reader_id || '';
                    this.pos.config.orbit_stripe_publishable_key =
                        data.publishable_key || '';
                }

                console.log(
                    '[OrbitStripe] Runtime config refreshed. testMode=%s reader=%s',
                    this._isTestMode(),
                    (data.reader_id || '(auto)')
                );
            } catch (err) {
                console.warn(
                    '[OrbitStripe] Runtime config refresh failed. Using cached POS config.',
                    err
                );
            }
        },

        _getConfiguredReaderId: function () {
            return (this.payment_method && this.payment_method.orbit_stripe_reader_id)
                || (this.pos.config && this.pos.config.orbit_stripe_reader_id)
                || '';
        },

        _sleep: function (ms) {
            return new Promise(resolve => setTimeout(resolve, ms));
        },

        _createTerminal: function () {
            if (typeof StripeTerminal === 'undefined') {
                console.error('[OrbitStripe] StripeTerminal SDK not loaded. Check CDN script tag.');
                return false;
            }
            try {
                this._terminal = StripeTerminal.create({
                    onFetchConnectionToken:       this._fetchConnectionToken.bind(this),
                    onUnexpectedReaderDisconnect: this._onReaderDisconnect.bind(this),
                });
                this._connected = false;
                console.log('[OrbitStripe] SDK ready. testMode=%s', this._isTestMode());
                return true;
            } catch (err) {
                console.error('[OrbitStripe] SDK create failed:', err);
                this._terminal = null;
                return false;
            }
        },

        // -------------------------------------------------------------------
        // Connection token — SDK calls this automatically when needed
        // -------------------------------------------------------------------

        _fetchConnectionToken: async function () {
            try {
                const data = await rpc.query({
                    model:  'pos.payment.method',
                    method: 'orbit_stripe_connection_token',
                    kwargs: { context: this.pos.env.session.user_context },
                }, { silent: true });
                if (data && data.error) { throw new Error(data.error); }
                if (data && data.secret) { return data.secret; }
                throw new Error('No connection token returned from server.');
            } catch (err) {
                const msg = this._errorMessage(err);
                console.error('[OrbitStripe] Connection token failed:', msg);
                this._terminal = null;
                this._connected = false;
                this._showError(msg, _t('Stripe Connection Error'));
            }
        },

        _onReaderDisconnect: function () {
            console.warn('[OrbitStripe] Reader disconnected unexpectedly.');
            this._connected = false;
            this._showError(
                _t('The card reader disconnected. Please reconnect and try again.'),
                _t('Reader Disconnected')
            );
        },

        // ===================================================================
        // Reader discovery & connection
        // ===================================================================

        _discoverAndConnect: async function (line) {
            if (!this._terminal) {
                if (!this._createTerminal()) {
                    this._showError(
                        _t('Stripe Terminal SDK failed to load. Reload the POS and try again.'),
                        _t('SDK Error')
                    );
                    return false;
                }
            }

            // Already connected — reuse connection
            if (this._connected &&
                this._terminal.getConnectionStatus() === 'connected') {
                return true;
            }

            // Discover readers
            const simulated = this._isTestMode();
            const discoverConfig = simulated ? { simulated: true } : {};
            console.log('[OrbitStripe] Discovering readers... (simulated=%s)', simulated);

            const discoverResult = await this._terminal.discoverReaders(discoverConfig);
            if (discoverResult.error) {
                this._showError(
                    discoverResult.error.message || String(discoverResult.error),
                    _t('Reader Discovery Failed')
                );
                line && line.set_payment_status('retry');
                return false;
            }

            const readers = discoverResult.discoveredReaders || [];
            if (!readers.length) {
                this._showError(
                    simulated
                        ? _t('No simulated readers found.\n\n' +
                             'Go to Settings → Stripe Terminal → Setup Wizard ' +
                             'and click "Create Simulated Reader".')
                        : _t('No Stripe readers found.\n\n' +
                             'Ensure your reader is:\n' +
                             '  • Powered on\n' +
                             '  • Connected to the same network as this computer\n' +
                             '  • Registered in Stripe Dashboard → Terminal → Readers'),
                    _t('No Readers Found')
                );
                line && line.set_payment_status('retry');
                return false;
            }

            console.log('[OrbitStripe] Discovered %d reader(s):', readers.length,
                readers.map(r => r.id + ' ' + (r.label || '')).join(', '));

            // Select reader: prefer configured ID, otherwise use first discovered
            const configuredId = (this.payment_method && this.payment_method.orbit_stripe_reader_id)
                || (this.pos.config && this.pos.config.orbit_stripe_reader_id)
                || '';

            let selectedReader = readers[0];
            if (configuredId) {
                const match = readers.find(r => r.id === configuredId);
                if (match) {
                    selectedReader = match;
                } else {
                    console.warn(
                        '[OrbitStripe] Configured reader "%s" not found. Using first: "%s".',
                        configuredId, readers[0].id
                    );
                }
            }

            console.log('[OrbitStripe] Connecting to reader:', selectedReader.id);
            const connectResult = await this._terminal.connectReader(selectedReader);
            if (connectResult.error) {
                this._showError(
                    connectResult.error.message || String(connectResult.error),
                    _t('Reader Connection Failed')
                );
                line && line.set_payment_status('retry');
                return false;
            }

            this._connected = true;
            console.log('[OrbitStripe] Connected to reader:', selectedReader.id,
                selectedReader.label || '');
            return true;
        },

        _processConfiguredReaderPayment: async function (paymentIntentId, line) {
            let readerResult;
            const readerId = this._getConfiguredReaderId();
            line.set_payment_status('waitingCard');
            console.log(
                '[OrbitStripe] Using configured reader "%s" via server-side Stripe API.',
                readerId
            );

            try {
                readerResult = await rpc.query({
                    model: 'pos.payment.method',
                    method: 'orbit_stripe_process_reader_payment',
                    args: [[this.payment_method.id], paymentIntentId],
                    kwargs: { context: this.pos.env.session.user_context },
                }, { silent: true });
            } catch (err) {
                this._showError(this._errorMessage(err), _t('Reader Payment Error'));
                line.set_payment_status('retry');
                this._activeIntent = null;
                return false;
            }

            if (!readerResult || readerResult.error) {
                this._showError(
                    (readerResult && readerResult.error)
                    || _t('Failed to start payment on the configured Stripe reader.'),
                    _t('Reader Payment Error')
                );
                line.set_payment_status('retry');
                this._activeIntent = null;
                return false;
            }

            return await this._pollConfiguredReaderPayment(paymentIntentId, line);
        },

        _pollConfiguredReaderPayment: async function (paymentIntentId, line) {
            const maxAttempts = this._isTestMode() ? 15 : 60;
            const delayMs = this._isTestMode() ? 1000 : 2000;

            for (let attempt = 0; attempt < maxAttempts; attempt++) {
                if (this._activeIntent !== paymentIntentId) {
                    return false;
                }

                let intentData;
                try {
                    intentData = await rpc.query({
                        model: 'pos.payment.method',
                        method: 'orbit_stripe_retrieve_payment_intent',
                        args: [paymentIntentId],
                        kwargs: { context: this.pos.env.session.user_context },
                    }, { silent: true });
                } catch (err) {
                    this._showError(this._errorMessage(err), _t('Reader Polling Error'));
                    line.set_payment_status('retry');
                    this._activeIntent = null;
                    return false;
                }

                if (!intentData || intentData.error) {
                    this._showError(
                        (intentData && intentData.error)
                        || _t('Failed to retrieve Stripe payment status.'),
                        _t('Reader Polling Error')
                    );
                    line.set_payment_status('retry');
                    this._activeIntent = null;
                    return false;
                }

                const status = intentData.status || 'unknown';
                console.log(
                    '[OrbitStripe] Reader-driven PaymentIntent %s status=%s (attempt %s/%s)',
                    paymentIntentId, status, attempt + 1, maxAttempts
                );

                if (status === 'requires_capture') {
                    line.set_payment_status('waitingCapture');
                    const captured = await this._captureIntent(paymentIntentId, line);
                    this._activeIntent = null;
                    if (!captured) { return false; }
                    line.set_payment_status('done');
                    return true;
                }

                if (status === 'succeeded') {
                    const autoCapture = this._checkAutoCapture(intentData);
                    if (autoCapture) {
                        line.card_type = autoCapture.brand;
                        line.transaction_id = autoCapture.charge_id;
                    } else {
                        line.transaction_id = intentData.id || paymentIntentId;
                    }
                    this._activeIntent = null;
                    line.set_payment_status('done');
                    return true;
                }

                if (status === 'canceled') {
                    this._showError(
                        _t('The Stripe reader payment was canceled before completion.'),
                        _t('Reader Payment Cancelled')
                    );
                    line.set_payment_status('retry');
                    this._activeIntent = null;
                    return false;
                }

                const lastPaymentError = intentData.last_payment_error;
                if (lastPaymentError && lastPaymentError.message) {
                    this._showError(
                        lastPaymentError.message,
                        lastPaymentError.code || _t('Card Error')
                    );
                    line.set_payment_status('retry');
                    this._activeIntent = null;
                    return false;
                }

                await this._sleep(delayMs);
            }

            this._showError(
                _t('Timed out waiting for the configured Stripe reader to finish the payment.\n\n' +
                   'Check the reader screen and network status, then try again.'),
                _t('Reader Timeout')
            );
            line.set_payment_status('retry');
            this._activeIntent = null;
            return false;
        },

        // ===================================================================
        // Payment collection
        // ===================================================================

        _doPayment: async function (line) {
            // Step 1: Create PaymentIntent server-side
            const amount = line.amount;
            let intentData;
            try {
                intentData = await rpc.query({
                    model:  'pos.payment.method',
                    method: 'orbit_stripe_payment_intent',
                    args:   [[this.payment_method.id], amount],
                    kwargs: { context: this.pos.env.session.user_context },
                }, { silent: true });
            } catch (err) {
                this._showError(this._errorMessage(err), _t('Payment Intent Error'));
                line.set_payment_status('retry');
                return false;
            }

            if (!intentData || intentData.error) {
                this._showError(
                    (intentData && intentData.error) || _t('Failed to create payment intent.'),
                    _t('Payment Intent Error')
                );
                line.set_payment_status('retry');
                return false;
            }

            const paymentIntentId = intentData.id;
            this._activeIntent    = paymentIntentId;
            line.transaction_id   = paymentIntentId;

            const configuredReaderId = this._getConfiguredReaderId();
            if (configuredReaderId) {
                return await this._processConfiguredReaderPayment(paymentIntentId, line);
            }

            const clientSecret    = intentData.client_secret;

            // Step 2: Collect payment method (customer taps card/phone)
            line.set_payment_status('waitingCard');
            console.log('[OrbitStripe] Collecting payment. Waiting for card tap...');

            const collectResult = await this._terminal.collectPaymentMethod(clientSecret);
            this._activeIntent = null;

            if (collectResult.error) {
                if (collectResult.error.code === 'canceled') {
                    // Cashier pressed Cancel — don't show error
                    return false;
                }
                this._showError(
                    collectResult.error.message || String(collectResult.error),
                    collectResult.error.decline_code || _t('Card Error')
                );
                line.set_payment_status('retry');
                return false;
            }

            // Step 3: Process the payment (cryptographic confirmation with Stripe)
            line.set_payment_status('waitingCapture');
            console.log('[OrbitStripe] Processing payment...');

            const processResult = await this._terminal.processPayment(
                collectResult.paymentIntent
            );

            if (processResult.error) {
                this._showError(
                    processResult.error.message || String(processResult.error),
                    processResult.error.code || _t('Processing Error')
                );
                line.set_payment_status('retry');
                return false;
            }

            if (!processResult.paymentIntent) {
                this._showError(_t('Unexpected response from Stripe. Please try again.'));
                line.set_payment_status('retry');
                return false;
            }

            const processedIntent = processResult.paymentIntent;
            line.transaction_id = processedIntent.id;

            // Step 4: Capture — some card types (Interac CA) auto-capture
            const autoCapture = this._checkAutoCapture(processedIntent);
            if (autoCapture) {
                line.card_type      = autoCapture.brand;
                line.transaction_id = autoCapture.charge_id;
            } else {
                const captured = await this._captureIntent(processedIntent.id, line);
                if (!captured) { return false; }
            }

            line.set_payment_status('done');
            console.log('[OrbitStripe] Payment complete. transaction_id=%s', line.transaction_id);
            return true;
        },

        _captureIntent: async function (paymentIntentId, line) {
            let captureData;
            try {
                captureData = await rpc.query({
                    model:  'pos.payment.method',
                    method: 'orbit_stripe_capture_payment',
                    args:   [paymentIntentId],
                    kwargs: { context: this.pos.env.session.user_context },
                }, { silent: true });
            } catch (err) {
                this._showError(this._errorMessage(err), _t('Capture Error'));
                line.set_payment_status('retry');
                return false;
            }

            if (!captureData || captureData.error) {
                this._showError(
                    (captureData && captureData.error) || _t('Failed to capture payment.'),
                    _t('Capture Error')
                );
                line.set_payment_status('retry');
                return false;
            }

            // Extract card brand — new Stripe API uses _charge (attached server-side)
            const charge = captureData._charge;
            if (charge && charge.payment_method_details) {
                line.card_type = this._getCardBrand(charge.payment_method_details);
            }
            // Fallback: old charges.data array
            if (!line.card_type) {
                const charges = captureData.charges;
                if (charges && charges.data && charges.data[0]) {
                    line.card_type = this._getCardBrand(charges.data[0].payment_method_details || {});
                }
            }
            line.transaction_id = captureData.id;
            console.log('[OrbitStripe] Captured. transaction=%s card=%s', captureData.id, line.card_type);
            return true;
        },

        // ===================================================================
        // Helpers
        // ===================================================================

        _getCardBrand: function (details) {
            if (details.card_present)    { return details.card_present.brand    || 'card'; }
            if (details.interac_present) { return details.interac_present.brand || 'interac'; }
            return 'card';
        },

        _checkAutoCapture: function (intent) {
            /* Interac (CA) and some eftpos (AU) cards auto-capture after processPayment.
               Returns {brand, charge_id} if auto-captured, null otherwise. */
            const charges = intent.charges;
            if (!charges || !charges.data || !charges.data[0]) { return null; }
            const charge  = charges.data[0];
            const details = charge.payment_method_details;
            if (!details) { return null; }
            if (details.type === 'interac_present') {
                return { brand: 'interac', charge_id: charge.id };
            }
            const brand = this._getCardBrand(details);
            if (brand && brand.toLowerCase().includes('eftpos')) {
                return { brand, charge_id: charge.id };
            }
            return null;
        },

        _errorMessage: function (err) {
            try {
                if (!err) { return _t('Unknown error'); }
                if (typeof err === 'string') { return err; }
                if (err.message) {
                    if (err.message.data && err.message.data.message) {
                        return err.message.data.message;
                    }
                    if (typeof err.message === 'string') { return err.message; }
                }
                return String(err);
            } catch (_) {
                return _t('An unexpected error occurred.');
            }
        },

        _showError: function (msg, title) {
            Gui.showPopup('ErrorPopup', {
                title: title || _t('Stripe Terminal Error'),
                body:  msg || _t('An error occurred.'),
            });
        },

        // ===================================================================
        // PaymentInterface overrides (called by Odoo POS)
        // ===================================================================

        send_payment_request: async function (cid) {
            await this._super(...arguments);
            const line = this.pos.get_order().selected_paymentline;
            line.set_payment_status('waiting');

            try {
                await this._refreshRuntimeConfig();
                if (!this._getConfiguredReaderId()) {
                    const connected = await this._discoverAndConnect(line);
                    if (!connected) { return false; }
                }
                return await this._doPayment(line);
            } catch (err) {
                console.error('[OrbitStripe] send_payment_request error:', err);
                this._showError(this._errorMessage(err));
                line.set_payment_status('retry');
                return false;
            }
        },

        send_payment_cancel: async function (order, cid) {
            this._super(...arguments);
            const line = this.pos.get_order().selected_paymentline;
            const configuredReaderId = this._getConfiguredReaderId();

            // Cancel SDK collection
            if (this._terminal &&
                this._terminal.getConnectionStatus() === 'connected') {
                try {
                    await this._terminal.cancelCollectPaymentMethod();
                } catch (e) {
                    console.warn('[OrbitStripe] cancelCollectPaymentMethod failed (non-fatal):', e);
                }
            }

            // Cancel reader action server-side for configured-reader mode
            if (configuredReaderId) {
                rpc.query({
                    model: 'pos.payment.method',
                    method: 'orbit_stripe_cancel_reader_action',
                    args: [[this.payment_method.id]],
                    kwargs: { context: this.pos.env.session.user_context },
                }, { silent: true }).catch(e =>
                    console.warn('[OrbitStripe] Cancel reader action failed (non-fatal):', e)
                );
            }

            // Cancel the PaymentIntent server-side
            const intentId = (line && line.transaction_id) || this._activeIntent;
            if (intentId) {
                rpc.query({
                    model:  'pos.payment.method',
                    method: 'orbit_stripe_cancel_payment',
                    args:   [intentId],
                    kwargs: { context: this.pos.env.session.user_context },
                }, { silent: true }).catch(e =>
                    console.warn('[OrbitStripe] Cancel PI server-side failed (non-fatal):', e)
                );
            }

            this._activeIntent = null;
            line && line.set_payment_status('retry');
            return true;
        },

        send_payment_reversal: async function (cid) {
            /* Refunds must be processed via the Stripe Dashboard or the
               Odoo backend Stripe Terminal Payments menu.
               Returning false delegates to POS standard reversal flow. */
            this._showError(
                _t('To refund a Stripe Terminal payment, go to:\n' +
                   'Point of Sale → Stripe Terminal Payments → find the payment → Cancel/Refund.\n\n' +
                   'Or process the refund directly in the Stripe Dashboard.'),
                _t('Refund via Backend')
            );
            return false;
        },

        close: function () {
            if (this._terminal &&
                this._terminal.getConnectionStatus() === 'connected') {
                this._terminal.disconnectReader().catch(e =>
                    console.warn('[OrbitStripe] disconnectReader on close:', e)
                );
            }
            this._connected = false;
        },

    });

    return OrbitStripePayment;
});
