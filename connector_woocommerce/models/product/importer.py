# Copyright 2009 Tech-Receptives Solutions Pvt. Ltd.
# Copyright 2018 FactorLibre
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging
import urllib.request
import urllib.error
import urllib.parse
import base64

from odoo.addons.component.core import Component
from odoo.addons.connector.components.mapper import mapping
from odoo.addons.connector.exception import MappingError

_logger = logging.getLogger(__name__)


class ProductBatchImporter(Component):
    """ Import the WooCommerce Products.

    For every product in the list, a delayed job is created.
    """
    _name = 'woocommerce.product.product.batch.importer'
    _inherit = 'woocommerce.delayed.batch.importer'
    _apply_on = ['woo.product.product']

    def run(self, filters=None):
        """ Run the synchronization """
        from_date = filters.pop('from_date', None)
        to_date = filters.pop('to_date', None)
        record_ids = self.backend_adapter.search(
            filters,
            from_date=from_date,
            to_date=to_date,
        )
        _logger.debug('search for woo Products %s returned %s',
                      filters, record_ids)
        for record_id in record_ids:
            self._import_record(record_id)


class ProductProductImporter(Component):
    _name = 'woocommerce.product.product.importer'
    _inherit = 'woocommerce.importer'
    _apply_on = ['woo.product.product']

    def _import_dependencies(self):
        """ Import the dependencies for the record"""
        record = self.woo_record
        for woo_category in record['categories']:
            self._import_dependency(woo_category['id'],
                                    'woo.product.category')

    def _after_import(self, binding):
        """ Hook called at the end of the import """
        image_importer = self.component(usage='product.image.importer')
        image_importer.run(self.woo_record, binding)
        return


class ProductImageImporter(Component):

    """ Import images for a record.

    Usually called from importers, in ``_after_import``.
    For instance from the products importer.
    """
    _name = 'woocommerce.product.image.importer'
    _inherit = 'woocommerce.importer'
    _apply_on = ['woo.product.product']
    _usage = 'product.image.importer'

    def _get_images(self, storeview_id=None):
        return self.backend_adapter.get_images(self.external_id)

    def _sort_images(self, images):
        """ Returns a list of images sorted by their priority.
        An image with the 'image' type is the the primary one.
        The other images are sorted by their position.

        The returned list is reversed, the items at the end
        of the list have the higher priority.
        """
        if not images:
            return {}
        # place the images where the type is 'image' first then
        # sort them by the reverse priority (last item of the list has
        # the the higher priority)

    def _get_binary_image(self, image_data):
        url = image_data['src']
        try:
            request = urllib.request.Request(url)
            binary = urllib.request.urlopen(request)
        except urllib.error.HTTPError as err:
            if err.code == 404:
                # the image is just missing, we skip it
                return
            else:
                # we don't know why we couldn't download the image
                # so we propagate the error, the import will fail
                # and we have to check why it couldn't be accessed
                raise
        else:
            return binary.read()

    def _write_image_data(self, binding, binary, image_data):
        binding = binding.with_context(connector_no_export=True)
        binding.write({'image': base64.b64encode(binary)})

    def run(self, woo_record, binding):
        images = woo_record['images']
        binary = None
        while not binary and images:
            image_data = images.pop()
            binary = self._get_binary_image(image_data)
        if not binary:
            return
        self._write_image_data(binding, binary, image_data)


class ProductProductImportMapper(Component):
    _name = 'woocommerce.product.product.import.mapper'
    _inherit = 'woocommerce.import.mapper'
    _apply_on = 'woo.product.product'

    direct = [
        ('name', 'name'),
        ('description', 'description'),
        ('weight', 'weight'),
        ('price', 'list_price')
    ]

    @mapping
    def is_active(self, record):
        """Check if the product is active in Woo
        and set active flag in OpenERP
        status == 1 in Woo means active"""
        return {'active': record.get('catalog_visibility') == 'visible'}

    @mapping
    def type(self, record):
        if record['type'] == 'simple':
            return {'type': 'product'}

    @mapping
    def categories(self, record):
        woo_categories = record['categories']
        binder = self.binder_for('woo.product.category')

        category_ids = []
        main_categ_id = None

        for woo_category in woo_categories:
            cat = binder.to_internal(woo_category['id'], unwrap=True)
            if not cat:
                raise MappingError("The product category with "
                                   "woo id %s is not imported." %
                                   woo_category['id'])
            category_ids.append(cat.id)

        if category_ids:
            main_categ_id = category_ids.pop(0)

        result = {'categ_ids': [(6, 0, category_ids)]}
        if main_categ_id:  # OpenERP assign 'All Products' if not specified
            result['categ_id'] = main_categ_id
        return result

    @mapping
    def backend_id(self, record):
        return {'backend_id': self.backend_record.id}
