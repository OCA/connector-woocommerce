# -*- coding: utf-8 -*-
#
#
#    Tech-Receptives Solutions Pvt. Ltd.
#    Copyright (C) 2009-TODAY Tech-Receptives(<http://www.techreceptives.com>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
#

import logging
import xmlrpclib
from openerp import models, fields
from openerp.addons.connector.queue.job import job
from openerp.addons.connector.unit.mapper import (mapping,
                                                  ImportMapper
                                                  )
from openerp.addons.connector.exception import IDMissingInBackend
from ..unit.backend_adapter import (GenericAdapter)
from ..unit.import_synchronizer import (DelayedBatchImporter, WooImporter)
from ..connector import get_environment
from ..backend import woo
_logger = logging.getLogger(__name__)


class WooDeliveryMethod(models.Model):
    _name = 'woo.delivery.carrier'
    _inherit = 'woo.binding'
    _inherits = {'delivery.carrier': 'openerp_id'}
    _description = 'woo Delivery carrier'

    _rec_name = 'name'

    openerp_id = fields.Many2one(comodel_name='delivery.carrier',
                                 string='Delivery method',
                                 required=True,
                                 ondelete='cascade')
    backend_id = fields.Many2one(
        comodel_name='wc.backend',
        string='Woo Backend',
        store=True,
        readonly=False,
    )


@woo
class DeliveryAdapter(GenericAdapter):
    _model_name = 'woo.delivery.carrier'
    _woo_model = 'settings/shipping_options'

    def _call(self, method, arguments):
        try:
            return super(DeliveryAdapter, self)._call(method, arguments)
        except xmlrpclib.Fault as err:
            # this is the error in the WooCommerce API
            # when the customer does not exist
            if err.faultCode == 102:
                raise IDMissingInBackend
            else:
                raise

    def search(self, filters=None, from_date=None, to_date=None):
        """ Search records according to some criteria and return a
        list of ids

        :rtype: list
        """
        if filters is None:
            filters = {}
        WOO_DATETIME_FORMAT = '%Y/%m/%d %H:%M:%S'
        dt_fmt = WOO_DATETIME_FORMAT
        if from_date is not None:
            filters.setdefault('updated_at', {})
            filters['updated_at']['from'] = from_date.strftime(dt_fmt)
        if to_date is not None:
            filters.setdefault('updated_at', {})
            filters['updated_at']['to'] = to_date.strftime(dt_fmt)
        return self._call('settings/shipping_options/list',
                          [filters] if filters else [{}])


@woo
class DeliveryBatchImporter(DelayedBatchImporter):

    """ Import the WooCommerce Partners.

    For every partner in the list, a delayed job is created.
    """
    _model_name = ['woo.delivery.carrier']

    def _import_record(self, woo_id, priority=None):
        """ Delay a job for the import """

        super(DeliveryBatchImporter, self)._import_record(
            woo_id, priority=priority)

    def run(self, filters=None):
        """ Run the synchronization """
        from_date = filters.pop('from_date', None)
        to_date = filters.pop('to_date', None)
        record_ids = self.backend_adapter.search(
            filters,
            from_date=from_date,
            to_date=to_date,
        )
        _logger.info('search for woo Delivery Method %s returned %s',
                     filters, record_ids)
        for record_id in record_ids:
            self._import_record(record_id)

DeliveryBatchImporter = DeliveryBatchImporter


@woo
class DeliveryMethodImporter(WooImporter):
    _model_name = ['woo.delivery.carrier']

    def _import_dependencies(self):
        """ Import the dependencies for the record"""
        # import parent category
        # the root category has a 0 parent_id
        return

    def _create(self, data):
        openerp_binding = super(DeliveryMethodImporter, self)._create(data)
        return openerp_binding

    def _after_import(self, binding):
        """ Hook called at the end of the import """
        return

DeliveryMethodImporter = DeliveryMethodImporter


@woo
class DeliveryMethodImportMapper(ImportMapper):
    _model_name = 'woo.delivery.carrier'

    @mapping
    def name(self, record):
        if record['title']:
            return {'name': record['title']}

    @mapping
    def backend_id(self, record):
        return {'backend_id': self.backend_record.id}

    @mapping
    def product_id(self, record):
        return {'product_id': 3, 'parent_id': 1, 'partner_id': 1}
#


@job(default_channel='root.woo')
def delivery_method_import_batch(session, model_name, backend_id,
                                 filters=None):
    """ Prepare the import of Delivery method modified on WooCommerce """
    env = get_environment(session, model_name, backend_id)
    importer = env.get_connector_unit(DeliveryBatchImporter)
    importer.run(filters=filters)
