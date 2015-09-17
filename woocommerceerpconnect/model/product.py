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
import urllib2
import xmlrpclib
from collections import defaultdict
import base64
from openerp import models, fields, api
from openerp.addons.connector.queue.job import job, related_action
from openerp.addons.connector.exception import MappingError
from openerp.addons.connector.unit.synchronizer import (Importer, Exporter
                                                        )
from openerp.addons.connector.event import on_record_write
from ..related_action import unwrap_binding
from openerp.addons.connector.unit.mapper import (mapping,
                                                  ImportMapper
                                                  )
from openerp.addons.connector.exception import IDMissingInBackend
from ..unit.backend_adapter import (GenericAdapter)
from ..unit.import_synchronizer import (DelayedBatchImporter, WooImporter)
from ..connector import get_environment
from ..backend import woo

_logger = logging.getLogger(__name__)


def chunks(items, length):
    for index in xrange(0, len(items), length):
        yield items[index:index + length]


class WooProductTemplate(models.Model):
    _name = 'woo.product.template'
    _inherit = 'woo.binding'
    _inherits = {'product.template': 'openerp_id'}
    _description = 'woo product template'

    _rec_name = 'name'
    openerp_id = fields.Many2one(comodel_name='product.template',
                                 string='product',
                                 required=True,
                                 ondelete='cascade')
    backend_id = fields.Many2one(
        comodel_name='wc.backend',
        string='Woo Backend',
        store=True,
        readonly=False,
        required=True,
    )
    combinations_ids = fields.One2many(
        'woo.product.combination',
        'main_template_id',
        string='Combinations'
    )
    slug = fields.Char('Slung Name')
    credated_at = fields.Date('created_at')
    weight = fields.Float('weight')
    woo_qty = fields.Float(string='Computed Quantity',
                           help="Last computed quantity to send \
                           on WooCommerce.")
    no_stock_sync = fields.Boolean(
        string='No Stock Synchronization',
        required=False,
        help="Check this to exclude the product "
             "from stock synchronizations.",
    )

    RECOMPUTE_QTY_STEP = 1000  # products at a time

    @api.multi
    def recompute_woo_qty(self):
        """ Check if the quantity in the stock location configured
        on the backend has changed since the last export.

        If it has changed, write the updated quantity on `woo_qty`.
        The write on `woo_qty` will trigger an `on_record_write`
        event that will create an export job.

        It groups the products by backend to avoid to read the backend
        informations for each product.
        """
        # group products by backend
        backends = defaultdict(self.browse)
        for product in self:
            backends[product.backend_id] |= product

        for backend, products in backends.iteritems():
            self._recompute_woo_qty_backend(backend, products)
        return True

    @api.multi
    def _recompute_woo_qty_backend(self, backend, products,
                                   read_fields=None):
        """ Recompute the products quantity for one backend.

        If field names are passed in ``read_fields`` (as a list), they
        will be read in the product that is used in
        :meth:`~._woo_qty`.

        """

        if backend.product_stock_field_id:
            stock_field = backend.product_stock_field_id.name
        else:
            stock_field = 'virtual_available'
        product_fields = ['woo_qty', stock_field]
        if read_fields:
            product_fields += read_fields
        for chunk_ids in chunks(products.ids, self.RECOMPUTE_QTY_STEP):
            records = self.env['woo.product.template'].browse(chunk_ids)
            for product in records.read(fields=product_fields):
                new_qty = self._woo_qty(product, backend, stock_field)
                if new_qty != product['woo_qty']:
                    self.browse(product['id']).woo_qty = new_qty

    @api.multi
    def _woo_qty(self, product, backend, stock_field):
        """ Return the current quantity for one product."""
        return product[stock_field]


@woo
class ProductTemplateAdapter(GenericAdapter):
    _model_name = 'woo.product.template'
    _woo_model = 'products/details'

    def _call(self, method, arguments):
        try:
            return super(ProductTemplateAdapter, self)._call(method, arguments)
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
            # updated_at include the created records
            filters.setdefault('updated_at', {})
            filters['updated_at']['from'] = from_date.strftime(dt_fmt)
        if to_date is not None:
            filters.setdefault('updated_at', {})
            filters['updated_at']['to'] = to_date.strftime(dt_fmt)

        return self._call('products/list',
                          [filters] if filters else [{}])

    def get_images(self, id, storeview_id=None):
        return self._call('products/' + str(id), [int(id), storeview_id, 'id'])

    def read_image(self, id, image_name, storeview_id=None):
        return self._call('products',
                          [int(id), image_name, storeview_id, 'id'])

    def update_inventory(self, id, data):
        # product_stock.update is too slow
        return self._call_inventory('product_qty_update', [int(id), data])


@woo
class ProductBatchImporter(DelayedBatchImporter):

    """ Import the WooCommerce Partners.

    For every partner in the list, a delayed job is created.
    """
    _model_name = ['woo.product.template']

    def _import_record(self, woo_id, priority=None):
        """ Delay a job for the import """
        super(ProductBatchImporter, self)._import_record(
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
        _logger.info('search for woo Products %s returned %s',
                     filters, record_ids)
        for record_id in record_ids:
            self._import_record(record_id, 30)


ProductBatchImporter = ProductBatchImporter


@job
def import_record(session, model_name, backend_id, woo_id):
    """ Import a record from woocommerce """
    env = get_environment(session, model_name, backend_id)
    importer = env.get_connector_unit(WooImporter)
    importer.run(woo_id)


@woo
class ProductTemplateImporter(WooImporter):
    _model_name = ['woo.product.template']

    def _import_dependencies(self):
        """ Import the dependencies for the record"""
        record = self.woo_record
        record = record['product']
        for woo_category_id in record['categories']:
            self._import_dependency(woo_category_id,
                                    'woo.product.category')

    def _clean_woo_items(self, resource):
        """
        Method that clean the sale order line given by WooCommerce before
        importing it

        This method has to stay here because it allow to customize the
        behavior of the sale order.

        """
        top_items = []

        # Group the childs with their parent
        for item in resource['product']['attributes']:
            top_items.append(item)
        all_items = []
        for top_item in top_items:
            all_items.append(top_item)
        resource['attributes'] = all_items
        return resource

    def _create(self, data):
        openerp_binding = super(ProductTemplateImporter, self)._create(data)
        return openerp_binding

    def _after_import(self, binding):
        """ Hook called at the end of the import """
        image_importer = self.unit_for(ProductImageImporter)
        image_importer.run(self.woo_id, binding.id)
        record = self.woo_record
        variations = record['product']['variations']
        for variation in variations:
            self._import_dependency(variation['id'],
                                    'woo.product.combination')
        self.attribute_line(self.woo_id)
        return

    def attribute_line(self, woo_id):
        template = self.env['woo.product.template'].search(
            [('woo_id', '=', woo_id)])
        template_id = template.openerp_id.id
        product_ids = self.session.search('product.product', [
            ('product_tmpl_id', '=', template_id)]
        )
        if product_ids:
            products = self.session.browse('product.product',
                                           product_ids)
            attribute_ids = []
            for product in products:
                for attribute_value in product.attribute_value_ids:
                    attribute_ids.append(attribute_value.attribute_id.id)
                    # filter unique id for create relation
            if attribute_ids:
                for attribute_id in set(attribute_ids):
                    value_ids = []
                    for product in products:
                        for attribute_value in product.attribute_value_ids:
                            if attribute_value.attribute_id.id == attribute_id:
                                value_ids.append(attribute_value.id)
                    line_id = self.env['product.attribute.line'].search(
                        [('attribute_id', '=', attribute_id),
                         ('product_tmpl_id', '=', template_id)])
                    if line_id:
                        self.env['product.attribute.line'].write({
                            'attribute_id': attribute_id,
                            'product_tmpl_id': template_id,
                            'value_ids': [(6, 0, set(value_ids))]}
                        )
                    else:
                        self.session.create('product.attribute.line', {
                                            'attribute_id': attribute_id,
                                            'product_tmpl_id': template_id,
                                            'value_ids': [(6, 0,
                                                           set(value_ids))]}
                                            )

ProductTemplateImport = ProductTemplateImporter


@woo
class ProductImageImporter(Importer):

    """ Import images for a record.

    Usually called from importers, in ``_after_import``.
    For instance from the products importer.
    """
    _model_name = ['woo.product.template'
                   ]

    def _get_images(self, storeview_id=None):
        return self.backend_adapter.get_images(self.woo_id)

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
        url = image_data['src'].encode('utf8')
        url = str(url).replace("\\", '')
        try:
            request = urllib2.Request(url)
            binary = urllib2.urlopen(request)
        except urllib2.HTTPError as err:
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

    def run(self, woo_id, binding_id):
        self.woo_id = woo_id
        images = self._get_images()
        images = images['product']
        images = images['images']
        binary = None
        while not binary and images:
            binary = self._get_binary_image(images.pop())
        if not binary:
            return
        model = self.model.with_context(connector_no_export=True)
        binding = model.browse(binding_id)
        binding.write({'image': base64.b64encode(binary)})


@woo
class ProductTemplateImportMapper(ImportMapper):
    _model_name = 'woo.product.template'

    direct = [
        ('description', 'description'),
        ('weight', 'weight'),
    ]

#     @mapping
#     def is_active(self, record):
#         """Check if the product is active in Woo
#         and set active flag in OpenERP
#         status == 1 in Woo means active"""
#         if record['product']:
#             rec = record['product']
#             return {'active': rec['visible']}

    @mapping
    def in_stock(self, record):
        if record['product']:
            rec = record['product']
            return {'in_stock': rec['in_stock']}

    @mapping
    def name(self, record):
        if record['product']:
            rec = record['product']
            return {'name': rec['title']}

    @mapping
    def type(self, record):
        if record['product']:
            rec = record['product']
            if rec['type'] == 'simple' or 'variable':
                return {'type': 'product'}

    @mapping
    def categories(self, record):
        if record['product']:
            rec = record['product']
            woo_categories = rec['categories']
            binder = self.binder_for('woo.product.category')
            category_ids = []
            main_categ_id = None
            for woo_category_id in woo_categories:
                cat_id = binder.to_openerp(woo_category_id, unwrap=True)
                if cat_id is None:
                    raise MappingError("The product category with "
                                       "woo id %s is not imported." %
                                       woo_category_id)
                category_ids.append(cat_id)
            if category_ids:
                main_categ_id = category_ids.pop(0)
            result = {'woo_categ_ids': [(6, 0, category_ids)]}
            if main_categ_id:  # OpenERP assign 'All Products' if not specified
                result['categ_id'] = main_categ_id
            return result

    @mapping
    def price(self, record):
        """ The price is imported at the creation of
        the product, then it is only modified and exported
        from OpenERP """
        if record['product']:
            rec = record['product']
            return {'list_price': rec and rec['price'] or 0.0}

    @mapping
    def sale_price(self, record):
        """ The price is imported at the creation of
        the product, then it is only modified and exported
        from OpenERP """
        if record['product']:
            rec = record['product']
            return {'standard_price': rec and rec['sale_price'] or 0.0}

    @mapping
    def backend_id(self, record):
        return {'backend_id': self.backend_record.id}


@job(default_channel='root.woo')
def product_import_batch(session, model_name, backend_id, filters=None):
    """ Prepare the import of product modified on Woo """
    if filters is None:
        filters = {}
    env = get_environment(session, model_name, backend_id)
    importer = env.get_connector_unit(ProductBatchImporter)
    importer.run(filters=filters)


@woo
class ProductTemplateInventoryExporter(Exporter):
    _model_name = ['woo.product.template']

    _map_backorders = {'use_default': 0,
                       'no': 0,
                       'yes': 1,
                       'yes-and-notification': 2,
                       }

    def _get_data(self, product, fields):
        result = {}
        if 'woo_qty' in fields:
            result.update({
                'qty': product.woo_qty,
                # put the stock availability to "out of stock"
                'is_in_stock': int(product.woo_qty > 0)
            })
        if 'manage_stock' in fields:
            manage = product.manage_stock
            result.update({
                'manage_stock': int(manage == 'yes'),
                'use_config_manage_stock': int(manage == 'use_default'),
            })
        if 'backorders' in fields:
            backorders = product.backorders
            result.update({
                'backorders': self._map_backorders[backorders],
                'use_config_backorders': int(backorders == 'use_default'),
            })
        return result

    def run(self, binding_id, fields):
        """ Export the product inventory to WooCommerce """
        product = self.model.browse(binding_id)
        woo_id = self.binder.to_backend(product.id)
        data = self._get_data(product, fields)
        self.backend_adapter.update_inventory(woo_id, data)


ProductTemplateInventoryExport = ProductTemplateInventoryExporter  # deprecated

# fields which should not trigger an export of the products
# but an export of their inventory
INVENTORY_FIELDS = ('manage_stock',
                    'woo_qty',
                    )


@on_record_write(model_names='woo.product.template')
def woo_product_modified(session, model_name, record_id, vals):
    if session.context.get('connector_no_export'):
        return
    if session.env[model_name].browse(record_id).no_stock_sync:
        return
    inventory_fields = list(set(vals).intersection(INVENTORY_FIELDS))
    if inventory_fields:
        export_product_inventory.delay(session, model_name,
                                       record_id, fields=inventory_fields,
                                       priority=20)


@job(default_channel='root.woo')
@related_action(action=unwrap_binding)
def export_product_inventory(session, model_name, record_id, fields=None):
    """ Export the inventory configuration and quantity of a product. """
    product = session.env[model_name].browse(record_id)
    backend_id = product.backend_id.id
    env = get_environment(session, model_name, backend_id)
    inventory_exporter = env.get_connector_unit(
        ProductTemplateInventoryExporter)
    return inventory_exporter.run(record_id, fields)
