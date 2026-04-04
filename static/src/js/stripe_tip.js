/* ===========================================================================
   Orbit Stripe Terminal — Tip / Gratuity Support
   ===========================================================================
   Simple tip selection using Odoo's built-in popups (no custom OWL component).
   Uses NumberPopup for custom amounts and SelectionPopup for presets.
   =========================================================================== */

odoo.define('orbit_stripe_contactless_payment.stripe_tip', function (require) {
    'use strict';

    const { Gui }          = require('point_of_sale.Gui');
    const SelectionPopup   = require('point_of_sale.SelectionPopup');
    const NumberPopup      = require('point_of_sale.NumberPopup');

    const TipUtils = {

        isTipEnabled(posConfig) {
            return posConfig && posConfig.orbit_stripe_tip_enabled === true;
        },

        getTipPercentages(posConfig) {
            const raw = posConfig && posConfig.orbit_stripe_tip_percentages;
            if (!raw) { return [10, 15, 20]; }
            return String(raw).split(',')
                .map(p => parseInt(p.trim()))
                .filter(p => !isNaN(p) && p > 0);
        },

        async showTipPopup(orderTotal, currency, percentages) {
            try {
                // Build selection items
                const items = [
                    {
                        id: 'no_tip',
                        label: 'No Tip',
                        item: 0,
                    },
                ];

                // Add percentage presets
                for (const pct of (percentages || [10, 15, 20])) {
                    const tipAmt = parseFloat((orderTotal * pct / 100).toFixed(2));
                    items.push({
                        id: `pct_${pct}`,
                        label: `${pct}%  —  ${currency}${tipAmt.toFixed(2)}`,
                        item: tipAmt,
                    });
                }

                // Add custom option
                items.push({
                    id: 'custom',
                    label: 'Custom amount...',
                    item: 'custom',
                });

                // Show selection popup
                const { confirmed: selConfirmed, payload: selection } = await Gui.showPopup(
                    'SelectionPopup',
                    {
                        title: `💰 Add a Tip? (Order: ${currency}${orderTotal.toFixed(2)})`,
                        list:  items,
                    }
                );

                if (!selConfirmed) { return 0; }

                // No tip
                if (selection === 0) { return 0; }

                // Custom amount — show number input
                if (selection === 'custom') {
                    const { confirmed: numConfirmed, payload: numStr } = await Gui.showPopup(
                        'NumberPopup',
                        {
                            title:      'Enter Tip Amount',
                            startingValue: '0',
                            isInputSelected: true,
                        }
                    );
                    if (!numConfirmed) { return 0; }
                    const custom = parseFloat(numStr);
                    return isNaN(custom) || custom < 0 ? 0 : custom;
                }

                // Preset percentage
                return parseFloat(selection) || 0;

            } catch (e) {
                console.warn('[OrbitStripe] Tip popup error (non-fatal):', e);
                return 0;
            }
        },
    };

    return { TipUtils };
});
