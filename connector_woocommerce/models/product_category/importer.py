# Copyright 2009 Tech-Receptives Solutions Pvt. Ltd.
# Copyright 2018 FactorLibre
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
import logging
from odoo.addons.component.core import Component
from odoo.addons.connector.components.mapper import mapping
from odoo.addons.connector.exception import MappingError

_logger = logging.getLogger(__name__)


class CategoryBatchImporter(Component):
    """ Import the WooCommerce Partners.

    For every partner in the list, a delayed job is created.
    """
    _name = 'woocommerce.product.category.batch.importer'
    _inherit = 'woocommerce.delayed.batch.importer'
    _apply_on = ['woo.product.category']

    def _import_record(self, external_id, job_options=None):
        """ Delay a job for the import """
        super(CategoryBatchImporter, self)._import_record(
            external_id, job_options=job_options)

    def run(self, filters=None):
        """ Run the synchronization """
        from_date = filters.pop('from_date', None)
        to_date = filters.pop('to_date', None)
        record_ids = self.backend_adapter.search(
            filters,
            from_date=from_date,
            to_date=to_date,
        )
        _logger.debug('search for woo Product Category %s returned %s',
                      filters, record_ids)
        for record_id in record_ids:
            self._import_record(record_id)


class ProductCategoryImporter(Component):
    _name = 'woocommerce.product.category.importer'
    _inherit = 'woocommerce.importer'
    _apply_on = ['woo.product.category']

    def _import_dependencies(self):
        """ Import the dependencies for the record"""
        record = self.woo_record
        # import parent category
        # the root category has a 0 parent_id
        if record.get('parent'):
            self._import_dependency(record.get('parent'), self.model)


class ProductCategoryImportMapper(Component):
    _name = 'woocommerce.product.category.import.mapper'
    _inherit = 'woocommerce.import.mapper'
    _apply_on = 'woo.product.category'

    direct = [
        ('name', 'name')
    ]

    @mapping
    def backend_id(self, record):
        return {'backend_id': self.backend_record.id}

    @mapping
    def parent_id(self, record):
        if not record.get('parent'):
            return
        binder = self.binder_for()
        parent_binding = binder.to_internal(record['parent'])

        if not parent_binding:
            raise MappingError("The product category with "
                               "woocommerce id %s is not imported." %
                               record['parent_id'])

        parent = parent_binding.odoo_id
        return {'parent_id': parent.id, 'woo_parent_id': parent_binding.id}
