# © 2009 Tech-Receptives Solutions Pvt. Ltd.
# © 2018 Serpent Consulting Services Pvt. Ltd.
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
# See LICENSE file for full copyright and licensing details.

import logging

from odoo.addons.component.core import Component
from odoo.addons.connector.components.mapper import mapping

_logger = logging.getLogger(__name__)


class CustomerBatchImporter(Component):
    """ Import the WooCommerce Partners.

    For every partner in the list, a delayed job is created.
    """
    _name = 'woo.partner.batch.importer'
    _inherit = 'woo.delayed.batch.importer'
    _apply_on = 'woo.res.partner'

    def _import_record(self, woo_id):
        """ Delay a job for the import """
        super(CustomerBatchImporter, self)._import_record(
            woo_id)

    def run(self, filters=None):
        """ Run the synchronization """
        from_date = filters.pop('from_date', None)
        to_date = filters.pop('to_date', None)
        # Get external ids with specific filters
        record_ids = self.backend_adapter.search(
            method='get',
            filters=filters,
            from_date=from_date,
            to_date=to_date,
        )
        customer_ref = self.env['woo.res.partner']
        record = []
        # Get external ids from odoo for comparison
        customer_rec = customer_ref.search([('external_id', '!=', '')])
        for ext_id in customer_rec:
            record.append(int(ext_id.external_id))
        # Get difference ids
        diff = list(set(record) - set(record_ids))
        for del_woo_rec in diff:
            woo_customer_id = customer_ref.search(
                [('external_id', '=', del_woo_rec)])
            cust_id = woo_customer_id.odoo_id
            odoo_customer_id = self.env['res.partner'].search(
                [('id', '=', cust_id.id)])
            # Delete reference from odoo
            odoo_customer_id.write({
                'woo_bind_ids': [(3, odoo_customer_id.woo_bind_ids[0].id)],
                'sync_data': False,
                'woo_backend_id': None
            })

        _logger.info('search for woo partners %s returned %s',
                     filters, record_ids)
        # Importing data
        for record_id in record_ids:
            self._import_record(record_id)


class CustomerImporter(Component):
    _name = 'woo.partner.importer'
    _inherit = 'woo.importer'
    _apply_on = 'woo.res.partner'

    def _import_dependencies(self):
        """ Import the dependencies for the record"""
        return

    def _create(self, data):
        odoo_binding = super(CustomerImporter, self)._create(data)
        # Adding Creation Checkpoint
        self.backend_record.add_checkpoint(odoo_binding)
        return odoo_binding

    def _update(self, binding, data):
        """ Update an Odoo record """
        super(CustomerImporter, self)._update(binding, data)
        # Adding updation checkpoint
        # self.backend_record.add_checkpoint(binding)
        return

    def _before_import(self):
        """ Hook called before the import"""
        return

    def _after_import(self, binding):
        """ Hook called at the end of the import """
        return


class CustomerImportMapper(Component):
    _name = 'woo.partner.import.mapper'
    _inherit = 'woo.import.mapper'
    _apply_on = 'woo.res.partner'

    @mapping
    def name(self, record):
        if record['customer']:
            rec = record['customer']
            return {'name': rec['first_name'] + " " + rec['last_name']}

    @mapping
    def email(self, record):
        if record['customer']:
            rec = record['customer']
            return {'email': rec['email'] or None}

    @mapping
    def city(self, record):
        if record['customer']:
            rec = record['customer']['billing_address']
            return {'city': rec['city'] or None}

    @mapping
    def zip(self, record):
        if record['customer']:
            rec = record['customer']['billing_address']
            return {'zip': rec['postcode'] or None}

    @mapping
    def address(self, record):
        if record['customer']:
            rec = record['customer']['billing_address']
            return {'street': rec['address_1'] or None}

    @mapping
    def address_2(self, record):
        if record['customer']:
            rec = record['customer']['billing_address']
            return {'street2': rec['address_2'] or None}

    @mapping
    def country(self, record):
        if record['customer']:
            rec = record['customer']['billing_address']
            if rec['country']:
                country_id = self.env['res.country'].search(
                    [('code', '=', rec['country'])])
                country_id = country_id.id
            else:
                country_id = False
            return {'country_id': country_id}

    @mapping
    def state(self, record):
        if record['customer']:
            rec = record['customer']['billing_address']
            if rec['state'] and rec['country']:
                state_id = self.env['res.country.state'].search(
                    [('code', '=', rec['state'])], limit=1)
                if not state_id:
                    country_id = self.env['res.country'].search(
                        [('code', '=', rec['country'])], limit=1)
                    state_id = self.env['res.country.state'].create(
                        {'name': rec['state'],
                         'code': rec['state'],
                         'country_id': country_id.id})
                state_id = state_id.id or False
            else:
                state_id = False
            return {'state_id': state_id}

    @mapping
    def backend_id(self, record):
        return {'backend_id': self.backend_record.id}

    # Required for export
    @mapping
    def sync_data(self, record):
        if record.get('customer'):
            return {'sync_data': True}

    @mapping
    def woo_backend_id(self, record):
        return {'woo_backend_id': self.backend_record.id}
