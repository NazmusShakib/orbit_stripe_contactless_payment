# -*- coding: utf-8 -*-
"""
Migration 16.0.1.1.0 — Add orbit_stripe_reader_id column to pos_payment_method
and register 'orbit_stripe_terminal' as a POS payment terminal option.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """
    Add orbit_stripe_reader_id (VARCHAR) column to pos_payment_method table
    if it does not already exist. Odoo's ORM will handle it on upgrade, but
    this pre-migration ensures the column exists before any onchange/compute
    triggers fire during the upgrade process.
    """
    cr.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'pos_payment_method'
          AND column_name = 'orbit_stripe_reader_id'
    """)
    if not cr.fetchone():
        _logger.info('Migration 16.0.1.1.0: Adding orbit_stripe_reader_id to pos_payment_method')
        cr.execute("""
            ALTER TABLE pos_payment_method
            ADD COLUMN orbit_stripe_reader_id VARCHAR
        """)
        _logger.info('Migration 16.0.1.1.0: orbit_stripe_reader_id column added successfully.')
    else:
        _logger.info('Migration 16.0.1.1.0: orbit_stripe_reader_id already exists, skipping.')
