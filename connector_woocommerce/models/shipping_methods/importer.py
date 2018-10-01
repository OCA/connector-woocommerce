# © 2009 Tech-Receptives Solutions Pvt. Ltd.
# © 2018 Serpent Consulting Services Pvt. Ltd.
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
# See LICENSE file for full copyright and licensing details.

import logging

from odoo.addons.component.core import Component
from odoo.addons.connector.components.mapper import mapping

_logger = logging.getLogger(__name__)


class DeliveryCarrierBatchImporter(Component):
    """ Import the WooCommerce Delivery Carrier.

    For every Delivery Carrier in the list, a delayed job is created.
    """
    _name = 'woo.delivery.carrier.batch.importer'
    _inherit = 'woo.delayed.batch.importer'
    _apply_on = 'woo.delivery.carrier'

    def _import_record(self, woo_id):
        """ Delay a job for the import """
        super(DeliveryCarrierBatchImporter, self)._import_record(
            woo_id)

    def run(self, filters=None):
        """ Run the synchronization """
        from_date = filters.pop('from_date', None)
        to_date = filters.pop('to_date', None)
        # Get external ids with specific filters
        record_ids = self.backend_adapter.search(method='get', filters=filters,
                                                 from_date=from_date,
                                                 to_date=to_date, )
        deliveryCarrier_ref = self.env['woo.delivery.carrier']
        record = []
        # Get external ids from odoo for comparison
        deliveryCarrier_rec = deliveryCarrier_ref.search(
            [('external_id', '!=', '')])
        for ext_id in deliveryCarrier_rec:
            record.append(int(ext_id.external_id))
        # Get difference ids
        diff = list(set(record) - set(record_ids))
        for del_woo_rec in diff:
            woo_DeliveryCarrier_id = deliveryCarrier_ref.search(
                [('external_id', '=', del_woo_rec)])
            cust_id = woo_DeliveryCarrier_id.odoo_id
            odoo_DeliveryCarrier_id = self.env['delivery.carrier'].search(
                [('id', '=', cust_id.id)])
            # Delete reference from odoo
            odoo_DeliveryCarrier_id.write({
                'woo_bind_ids': [
                    (3, odoo_DeliveryCarrier_id.woo_bind_ids[0].id)],
                'sync_data': False,
                'woo_backend_id': None
            })

        _logger.info('search for woo DeliveryCarrier %s returned %s',
                     filters, record_ids)
        # Importing data
        for record_id in record_ids:
            self._import_record(record_id)


class DeliveryCarrierImporter(Component):
    _name = 'woo.delivery.carrier.importer'
    _inherit = 'woo.importer'
    _apply_on = 'woo.delivery.carrier'

    def _import_dependencies(self):
        """ Import the dependencies for the record"""
        return

    def _create(self, data):
        odoo_binding = super(DeliveryCarrierImporter, self)._create(data)
        # Adding Creation Checkpoint
        self.backend_record.add_checkpoint(odoo_binding)
        return odoo_binding

    def _update(self, binding, data):
        """ Update an Odoo record """
        super(DeliveryCarrierImporter, self)._update(binding, data)
        return

    def _before_import(self):
        """ Hook called before the import"""
        return

    def _after_import(self, binding):
        """ Hook called at the end of the import """
        return


class DeliveryCarrierImportMapper(Component):
    _name = 'woo.delivery.carrier.import.mapper'
    _inherit = 'woo.import.mapper'
    _apply_on = 'woo.delivery.carrier'

    @mapping
    def name(self, record):
        if record['deliverycarier']:
            rec = record['deliverycarier']
            return {'name': rec['method_title']}
