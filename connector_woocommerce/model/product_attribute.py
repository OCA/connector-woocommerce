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


class WooProductAttribute(models.Model):
    _name = 'woo.product.attribute'
    _inherit = 'woo.binding'
    _inherits = {'product.attribute': 'openerp_id'}
    _description = 'woo product attribute'

    _rec_name = 'name'

    openerp_id = fields.Many2one(comodel_name='product.attribute',
                                 string='attribute',
                                 required=True,
                                 ondelete='cascade')
    backend_id = fields.Many2one(
        comodel_name='wc.backend',
        string='Woo Backend',
        store=True,
        readonly=False,
    )


@woo
class AttributeAdapter(GenericAdapter):
    _model_name = 'woo.product.attribute'
    _woo_model = 'products/attributes'

    def _call(self, method, arguments):
        try:
            return super(AttributeAdapter, self)._call(method, arguments)
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
        return self._call('products/attributes/list',
                          [filters] if filters else [{}])


@woo
class AttributeBatchImporter(DelayedBatchImporter):

    """ Import the WooCommerce Partners.

    For every partner in the list, a delayed job is created.
    """
    _model_name = ['woo.product.attribute']

    def _import_record(self, woo_id, priority=None):
        """ Delay a job for the import """

        super(AttributeBatchImporter, self)._import_record(
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
        _logger.info('search for woo Product Attribute %s returned %s',
                     filters, record_ids)
        for record_id in record_ids:
            self._import_record(record_id)
AttributeBatchImporter = AttributeBatchImporter


@woo
class ProductAttributeImporter(WooImporter):
    _model_name = ['woo.product.attribute']

    def _import_dependencies(self):
        """ Import the dependencies for the record"""
        return

    def _create(self, data):
        openerp_binding = super(ProductAttributeImporter, self)._create(data)
        return openerp_binding

    def _after_import(self, binding):
        """ Hook called at the end of the import """
        return

ProductAttributeImport = ProductAttributeImporter


@woo
class ProductAttributeImportMapper(ImportMapper):
    _model_name = 'woo.product.attribute'

    @mapping
    def name(self, record):
        if record['product_attribute']:
            rec = record['product_attribute']
            return {'name': rec['name']}

    @mapping
    def backend_id(self, record):
        return {'backend_id': self.backend_record.id}
#


@job(default_channel='root.woo')
def attribute_import_batch(session, model_name, backend_id, filters=None):
    """ Prepare the import of attribute modified on WooCommerce """
    env = get_environment(session, model_name, backend_id)
    importer = env.get_connector_unit(AttributeBatchImporter)
    importer.run(filters=filters)
