# -*- coding: utf-8 -*-
{
    'name': 'Orbit Stripe Contactless Terminal Integration',
    'version': '16.0.1.1.0',
    'category': 'Point of Sale',
    'summary': 'Stripe Terminal integration for in-person contactless card payments (Dev/Test Mode)',
    'description': """
Orbit Stripe Terminal Payment
==============================

Integrates Stripe Terminal for contactless in-person card payments.

Phase 1 — Developer / Test Mode:
- Simulated Stripe Terminal reader discovery and connection
- PaymentIntent creation via Stripe API
- Simulated card-present payment collection
- Payment status tracking and storage in Odoo

Features:
- Admin settings for Stripe API credentials (test mode only in Phase 1)
- Backend payment wizard: enter amount → create intent → simulate payment → confirm
- Full audit log of Stripe payment records in Odoo
- Ready to extend for real Stripe Terminal hardware in Phase 2

Note: This module uses Stripe's test/sandbox environment only.
      Real hardware support will be added in a future phase.
    """,
    'author': 'Nazmus Shakib',
    'website': 'https://github.com/NazmusShakib/orbit_stripe_contactless_payment/wiki',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'mail',
        'account',
        'point_of_sale',
    ],
    'data': [
        # Security
        'security/groups.xml',
        'security/ir.model.access.csv',
        # Data / configuration
        'data/ir_config_parameter_data.xml',
        'data/assets.xml',
        # Views
        'views/stripe_terminal_payment_views.xml',
        'views/stripe_setup_wizard_views.xml',
        'views/res_config_settings_views.xml',
        'views/assets_orbit_stripe.xml',
        'views/pos_payment_method_views.xml',
        'views/stripe_refund_wizard_views.xml',
        'views/menus.xml',
    ],
    'demo': [
        'demo/demo_data.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'orbit_stripe_contactless_payment/static/src/js/stripe_terminal_widget.js',
            'orbit_stripe_contactless_payment/static/src/css/stripe_terminal.css',
        ],
        'point_of_sale.assets': [
            # Tip support
            'orbit_stripe_contactless_payment/static/src/js/stripe_tip.js',
            # Main payment handler (two-phase: Send + Confirm)
            'orbit_stripe_contactless_payment/static/src/js/payment_orbit_stripe.js',
            # Payment method registration
            'orbit_stripe_contactless_payment/static/src/js/models_orbit_stripe.js',
            # PaymentScreenPaymentLines extension: Confirm button handler
            'orbit_stripe_contactless_payment/static/src/js/orbit_stripe_payment_lines.js',
            # XML template: Confirm button for waitingCapture status
            'orbit_stripe_contactless_payment/static/src/xml/OrbitStripePaymentLines.xml',
        ],
    },
    'images': [],
    'installable': True,
    'auto_install': False,
    'application': True,
    'external_dependencies': {
        'python': ['stripe'],
    },
}
