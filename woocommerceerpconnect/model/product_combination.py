# -*- coding: utf-8 -*-
#
#
#    Tech-Receptives Solutions Pvt. Ltd.
#    Copyright (C) 2004-TODAY Tech-Receptives(<http://www.tech-receptives.com>)
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

'''
A product combination is a product with different attributes in woo.
In woo, we can sell a product or a combination of a product with some
attributes.

For example, for the iPod product we can found in demo data, it has some
combinations with different colors and different storage size.

We map that in OpenERP to a product.product with an attribute.set defined for
the main product.
'''
import logging
import xmlrpclib
_logger = logging.getLogger(__name__)
from openerp.osv import fields, orm
from ..backend import woo
from openerp.addons.connector.exception import IDMissingInBackend
from openerp import SUPERUSER_ID
from openerp.addons.connector.unit.backend_adapter import BackendAdapter
from openerp.osv.orm import browse_record_list
# from .product import ProductInventoryExport
from ..unit.backend_adapter import (GenericAdapter)
# from .unit.import_synchronizer import WooImporter
from ..unit.import_synchronizer import (DelayedBatchImporter, WooImporter)
# from .unit.import_synchronizer import TranslatableRecordImport
from openerp.addons.connector.unit.mapper import (mapping,
                                                  ImportMapper
                                                  )


class product_product(orm.Model):
    _inherit = 'product.product'

    _columns = {
        'woo_combinations_bind_ids': fields.one2many(
            'woo.product.combination',
            'openerp_id',
            string='WooCommerce Bindings (combinations)'
        ),
    }


class woo_product_combination(orm.Model):
    _name = 'woo.product.combination'
    _inherit = 'woo.binding'
    _inherits = {'product.product': 'openerp_id'}

    _columns = {
        'openerp_id': fields.many2one(
            'product.product',
            string='Product',
            required=True,
            ondelete='cascade'
        ),
        'main_template_id': fields.many2one(
            'woo.product.template',
            string='Main Template',
            required=True,
            ondelete='cascade'
        ),
        'quantity': fields.float(
            'Computed Quantity',
            help="Last computed quantity to send on WooCommerce."
        ),
        'reference': fields.char('Original reference'),
        'default_on': fields.boolean('Available For Order'),
    }

    def recompute_woo_qty(self, cr, uid, ids, context=None):
        if not hasattr(ids, '__iter__'):
            ids = [ids]

        for product in self.browse(cr, uid, ids, context=context):
            new_qty = self._woo_qty(cr, uid, product, context=context)
            self.write(
                cr, uid, product.id, {'quantity': new_qty}, context=context
            )
        return True

    def _woo_qty(self, cr, uid, product, context=None):
        return product.qty_available


class product_attribute(orm.Model):
    _inherit = 'product.attribute'

    _columns = {
        'woo_bind_ids': fields.one2many(
            'woo.product.combination.option',
            'openerp_id',
            string='WooCommerce Bindings (combinations)'
        ),
    }


class woo_product_combination_option(orm.Model):
    _name = 'woo.product.combination.option'
    _inherit = 'woo.binding'
    _inherits = {'product.attribute': 'openerp_id'}

    _columns = {
        'openerp_id': fields.many2one(
            'product.attribute',
            string='Attribute',
            required=True,
            ondelete='cascade'
        ),
        'woo_position': fields.integer('WooCommerce Position'),
        'group_type': fields.selection([('color', 'Color'),
                                        ('radio', 'Radio'),
                                        ('select', 'Select')], 'Type'),
        'public_name': fields.char(
            'Public Name',
            translate=True
        ),

    }

    _defaults = {
        'group_type': 'select',
    }


class product_attribute_value(orm.Model):
    _inherit = 'product.attribute.value'

    _columns = {
        'woo_bind_ids': fields.one2many(
            'woo.product.combination.option.value',
            'openerp_id',
            string='WooCommerce Bindings'
        ),
    }


class woo_product_combination_option_value(orm.Model):
    _name = 'woo.product.combination.option.value'
    _inherit = 'woo.binding'
    _inherits = {'product.attribute.value': 'openerp_id'}

    _columns = {
        'openerp_id': fields.many2one(
            'product.attribute.value',
            string='Attribute',
            required=True,
            ondelete='cascade'
        ),
        'woo_position': fields.integer('WooCommerce Position'),
        'id_attribute_group': fields.many2one(
            'woo.product.combination.option')
    }

    _defaults = {
        'woo_position': 1
    }


@woo
class ProductCombinationAdapter(GenericAdapter):
    _model_name = 'woo.product.combination'
    _woo_model = 'products/details'

    def _call(self, method, arguments):
        try:
            return super(ProductCombinationAdapter,
                         self)._call(method, arguments)
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


@woo
class ProductCombinationBatchImporter(DelayedBatchImporter):

    """ Import the WooCommerce Partners.

    For every partner in the list, a delayed job is created.
    """
    _model_name = ['woo.product.combination']

    def _import_record(self, woo_id, priority=None):
        """ Delay a job for the import """
        super(ProductCombinationBatchImporter, self)._import_record(
            woo_id, priority=priority)

    def run(self, filters=None):
        """ Run the synchronization """
#
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


ProductCombinationBatchImporter = ProductCombinationBatchImporter


@woo
class ProductCombinationRecordImport(WooImporter):
    _model_name = 'woo.product.combination'

    def _import_dependencies(self):
        record = self.woo_record
        backend_adapter = self.get_connector_unit_for_model(
            BackendAdapter,
            'woo.product.combination.option.value'
        )
        variations = record['product']['combinations']
        for option_value in variations:
                option_value = backend_adapter.read(option_value['id'])
                self._import_dependency(
                    option_value['attribute_id'],
                    'woo.product.combination.option',
                )
                self._import_dependency(
                    option_value['term_id'],
                    'woo.product.combination.option.value'
                )

    def _create(self, data):
        openerp_binding = super(
            ProductCombinationRecordImport, self)._create(data)
        return openerp_binding

    def _after_import(self, erp_id):
#         self.woo_record
        return


@woo
class ProductCombinationMapper(ImportMapper):
    _model_name = 'woo.product.combination'

    from_main = []

    @mapping
    def product_tmpl_id(self, record):
        template = self.main_template(record)
        return {'product_tmpl_id': template.openerp_id.id}

    @mapping
    def from_main_template(self, record):
        main_template = self.main_template(record)
        result = {}
        for attribute in self.from_main:
            if attribute not in main_template:
                continue
            if hasattr(main_template[attribute], 'id'):
                result[attribute] = main_template[attribute].id
            elif type(main_template[attribute]) is browse_record_list:
                ids = []
                for element in main_template[attribute]:
                    ids.append(element.id)
                result[attribute] = [(6, 0, ids)]
            else:
                result[attribute] = main_template[attribute]
        return result

    def main_template(self, record):
        if hasattr(self, '_main_template'):
            return self._main_template
        template_id = self.get_main_template_id(record)
        self._main_template = self.session.browse(
            'woo.product.template',
            template_id)
        return self._main_template

    def get_main_template_id(self, record):
        template_binder = self.get_binder_for_model(
            'woo.product.template')
        record = record['product']
        if record['parent']:
            record = record['parent']
        return template_binder.to_openerp(record['id'])

    def _get_option_value(self, record):
        combinations = record['product']['combinations']
        if combinations:
                for option_value in combinations:
                    option_value_binder = self.get_binder_for_model(
                        'woo.product.combination.option.value')
                    option_value_openerp_id = option_value_binder.to_openerp(
                        option_value['id'])
                    option_value_object = self.session.browse(
                        'woo.product.combination.option.value',
                        option_value_openerp_id
                    )
                    yield option_value_object

    @mapping
    def name(self, record):
        template = self.main_template(record)
        options = []
        for option_value_object in self._get_option_value(record):
            key = option_value_object.attribute_id.name
            value = option_value_object.name
            options.append('%s:%s' % (key, value))
        return {'name_template': template.name}

    @mapping
    def attribute_value_ids(self, record):
        results = []
        for option_value_object in self._get_option_value(record):
            results.append(option_value_object.openerp_id.id)
        return {'attribute_value_ids': [(6, 0, set(results))]}

    @mapping
    def main_template_id(self, record):
        return {'main_template_id': self.get_main_template_id(record)}

    def _template_code_exists(self, code):
        model = self.session.pool.get('product.template')
        template_ids = model.search(self.session.cr, SUPERUSER_ID, [
            ('default_code', '=', code),
            ('company_id', '=', self.backend_record.company_id.id),
        ])
        return len(template_ids) > 0

    @mapping
    def backend_id(self, record):
        return {'backend_id': self.backend_record.id}


@woo
class ProductCombinationOptionAdapter(GenericAdapter):
    _model_name = 'woo.product.combination.option'
    _woo_model = 'products/attributes'


@woo
class ProductCombinationOptionRecordImport(WooImporter):
    _model_name = 'woo.product.combination.option'

    def _import_values(self):
        record = self.woo_record
        option_values = record.get('associations', {}).get(
            'product_option_values', {}).get('product_option_value', [])
        if not isinstance(option_values, list):
            option_values = [option_values]
        for option_value in option_values:
            self._check_dependency(
                option_value['id'],
                'woo.product.combination.option.value'
            )

    def run(self, ext_id):
        # looking for an product.attribute with the same name
        self.woo_id = ext_id
        self.woo_record = self._get_woo_data()
        name = self.mapper.name(self.woo_record)['name']
        attribute_ids = self.session.search('product.attribute',
                                            [('name', '=', name)])
        if len(attribute_ids) == 0:
            # if we don't find it, we create a woo_product_combination
            super(ProductCombinationOptionRecordImport, self).run(ext_id)
        else:
            # else, we create only a woo.product.combination.option
            data = {
                'openerp_id': attribute_ids[0],
                'backend_id': self.backend_record.id,
            }
            erp_id = self.model.create(data)
            self.binder.bind(self.woo_id, erp_id)

        self._import_values()


@woo
class ProductCombinationOptionMapper(ImportMapper):
    _model_name = 'woo.product.combination.option'

    direct = []

    @mapping
    def backend_id(self, record):
        return {'backend_id': self.backend_record.id}

    @mapping
    def name(self, record):
        if record['product_attribute']:
            rec = record['product_attribute']
            return {'name': rec['name']}


@woo
class ProductCombinationOptionValueAdapter(GenericAdapter):
    _model_name = 'woo.product.combination.option.value'
    _woo_model = 'products/variations'


@woo
class ProductCombinationOptionValueRecordImport(WooImporter):
    _model_name = 'woo.product.combination.option.value'

    def _import_values(self):
        record = self.woo_record
        option_values = record.get('associations', {}).get(
            'product_option_values', {}).get('product_option_value', [])
        if not isinstance(option_values, list):
            option_values = [option_values]
        for option_value in option_values:
            self._check_dependency(
                option_value['id'],
                'woo.product.combination.option.value'
            )

    def run(self, ext_id):
        # looking for an product.attribute with the same name
        self.woo_id = ext_id
        self.woo_record = self._get_woo_data()
        name = self.mapper.name(self.woo_record)['name']
        attribute_ids = self.session.search('product.attribute.value',
                                            [('name', '=', name)])
        if len(attribute_ids) == 0:
            # if we don't find it, we create a woo_product_combination
            super(ProductCombinationOptionValueRecordImport, self).run(ext_id)
        else:
            # else, we create only a woo.product.combination.option
            data = {
                'openerp_id': attribute_ids[0],
                'backend_id': self.backend_record.id,
            }
            erp_id = self.model.create(data)
            self.binder.bind(self.woo_id, erp_id)


@woo
class ProductCombinationOptionValueMapper(ImportMapper):
    _model_name = 'woo.product.combination.option.value'

    direct = []

    @mapping
    def name(self, record):
        return {'name': record['name']}

    @mapping
    def attribute_id(self, record):
        binder = self.get_binder_for_model(
            'woo.product.combination.option')
        attribute_id = binder.to_openerp(record['attribute_id'],
                                         unwrap=True)

        return {'attribute_id': attribute_id}

    @mapping
    def backend_id(self, record):
        return {'backend_id': self.backend_record.id}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
