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

from openerp import models, api, fields, _
from woocommerce import API
from openerp.exceptions import Warning
from openerp.addons.connector.session import ConnectorSession
from datetime import datetime
from .product_category import category_import_batch
from .product import product_import_batch
from .customer import customer_import_batch
from .sale import sale_order_import_batch
from .payment import payment_method_import_batch
from .delivery import delivery_method_import_batch
from ..unit.import_synchronizer import import_batch


class wc_backend(models.Model):
    _name = 'wc.backend'
    _inherit = 'connector.backend'
    _description = 'WooCommerce Backend Configuration'

    @api.model
    def _get_stock_field_id(self):
        field = self.env['ir.model.fields'].search(
            [('model', '=', 'product.product'),
             ('name', '=', 'virtual_available')], limit=1)
        return field
    name = fields.Char(string='name')
    _backend_type = 'woo'
    location = fields.Char("Url")
    consumer_key = fields.Char("Consumer key")
    consumer_secret = fields.Char("Consumer Secret")
    version = fields.Selection([('v2', 'v2')], 'Version')
    verify_ssl = fields.Boolean("Verify SSL")
    default_lang_id = fields.Many2one(
        comodel_name='res.lang',
        string='Default Language',
        help="If a default language is selected, the records "
             "will be imported in the translation of this language.\n"
             "Note that a similar configuration exists "
             "for each storeview.",
    )
    product_stock_field_id = fields.Many2one(
        comodel_name='ir.model.fields', string='Stock Field',
        default=_get_stock_field_id,
        domain="[('model', 'in', ['product.product', 'product.template']),"
               " ('ttype', '=', 'float')]",
        help="Choose the field of the product which will be used for "
             "stock inventory updates.\nIf empty, Quantity Available "
             "is used.",
    )

    def synchronize_basedata(self, cr, uid, ids, context=None):
        if not hasattr(ids, '__iter__'):
            ids = [ids]
        session = ConnectorSession(cr, uid, context=context)
        for backend_id in ids:
            import_batch(session, 'woo.res.currency', backend_id)
            import_batch(session, 'woo.configuration', backend_id)
            import_batch(session, 'woo.sale.order.state', backend_id)
        return True

    @api.multi
    def get_product_ids(self, data):
        product_ids = [x['id'] for x in data['products']]
        product_ids = sorted(product_ids)
        return product_ids

    @api.multi
    def get_product_category_ids(self, data):
        product_category_ids = [x['id'] for x in data['product_categories']]
        product_category_ids = sorted(product_category_ids)
        return product_category_ids

    @api.multi
    def get_customer_ids(self, data):
        customer_ids = [x['id'] for x in data['customers']]
        customer_ids = sorted(customer_ids)
        return customer_ids

    @api.multi
    def get_order_ids(self, data):
        order_ids = self.check_existing_order(data)
        return order_ids

    @api.multi
    def update_existing_order(self, woo_sale_order, data):
        """ Enter Your logic for Existing Sale Order """
        return True

    @api.multi
    def check_existing_order(self, data):
        order_ids = []
        for val in data['orders']:
            woo_sale_order = self.env['woo.sale.order'].search(
                [('woo_id', '=', val['id'])])
            if woo_sale_order:
                self.update_existing_order(woo_sale_order[0], val)
                continue
            order_ids.append(val['id'])
        return order_ids

    @api.multi
    def test_connection(self):
        location = self.location
        cons_key = self.consumer_key
        sec_key = self.consumer_secret
        version = 'v2'

        wcapi = API(url=location, consumer_key=cons_key,
                    consumer_secret=sec_key, version=version)
        r = wcapi.get("products")
        if r.status_code == 404:
            raise Warning(_("Enter Valid url"))
        val = r.json()
        msg = ''
        if 'errors' in r.json():
            msg = val['errors'][0]['message'] + '\n' + val['errors'][0]['code']
            raise Warning(_(msg))
        else:
            raise Warning(_('Test Success'))
        return True

    @api.multi
    def import_category(self):
        session = ConnectorSession(self.env.cr, self.env.uid,
                                   context=self.env.context)
        import_start_time = datetime.now()
        backend_id = self.id
        from_date = None
        category_import_batch.delay(
            session, 'woo.product.category', backend_id,
            {'from_date': from_date,
             'to_date': import_start_time}, priority=1)
        return True

    @api.multi
    def import_product(self):
        session = ConnectorSession(self.env.cr, self.env.uid,
                                   context=self.env.context)
        import_start_time = datetime.now()
        backend_id = self.id
        from_date = None
        product_import_batch.delay(
            session, 'woo.product.template', backend_id,
            {'from_date': from_date,
             'to_date': import_start_time}, priority=2)
        return True

    @api.multi
    def import_customer(self):
        session = ConnectorSession(self.env.cr, self.env.uid,
                                   context=self.env.context)
        import_start_time = datetime.now()
        backend_id = self.id
        from_date = None
        customer_import_batch.delay(
            session, 'woo.res.partner', backend_id,
            {'from_date': from_date,
             'to_date': import_start_time}, priority=3)
        return True

    @api.multi
    def import_order(self):
        session = ConnectorSession(self.env.cr, self.env.uid,
                                   context=self.env.context)
        import_start_time = datetime.now()
        backend_id = self.id
        from_date = None
        sale_order_import_batch.delay(
            session, 'woo.sale.order', backend_id,
            {'from_date': from_date,
             'to_date': import_start_time}, priority=4)
        return True

    @api.multi
    def import_payment_method(self):
        session = ConnectorSession(self.env.cr, self.env.uid,
                                   context=self.env.context)
        import_start_time = datetime.now()
        backend_id = self.id
        from_date = None
        payment_method_import_batch.delay(
            session, 'woo.payment.method', backend_id,
            {'from_date': from_date,
             'to_date': import_start_time}, priority=4)
        return True

    @api.multi
    def import_delivery_method(self):
        session = ConnectorSession(self.env.cr, self.env.uid,
                                   context=self.env.context)
        import_start_time = datetime.now()
        backend_id = self.id
        from_date = None
        delivery_method_import_batch.delay(
            session, 'woo.delivery.carrier', backend_id,
            {'from_date': from_date,
             'to_date': import_start_time}, priority=4)
        return True

    @api.multi
    def import_categories(self):
        """ Import Product categories """
        for backend in self:
            backend.import_category()
        return True

    @api.multi
    def import_products(self):
        """ Import categories from all websites """
        for backend in self:
            backend.import_product()
        return True

    @api.multi
    def import_customers(self):
        """ Import categories from all websites """
        for backend in self:
            backend.import_customer()
        return True

    @api.multi
    def import_orders(self):
        """ Import Orders from all websites """
        for backend in self:
            backend.import_order()
        return True

    @api.multi
    def import_payment_methods(self):
        """ Import Payment Methods from all websites """
        for backend in self:
            backend.import_payment_method()
        return True

    @api.multi
    def import_delivery_methods(self):
        """ Import Payment Methods from all websites """
        for backend in self:
            backend.import_delivery_method()
        return True

    @api.multi
    def _domain_for_update_product_stock_qty(self):
        return [
            ('backend_id', 'in', self.ids),
            ('type', '!=', 'service'),
        ]

    @api.multi
    def update_product_stock_qty(self):
        woo_product_obj = self.env['woo.product.combination']
        woo_product_template_obj = self.env['woo.product.template']
        domain = self._domain_for_update_product_stock_qty()
        woo_products = woo_product_obj.search(domain)
        template_id = woo_products.recompute_woo_qty()
        woo_product_template = woo_product_template_obj.search(domain)
        woo_product_template = [
            x for x in woo_product_template if x != template_id]
        if woo_product_template:
            for template in woo_product_template:
                template.recompute_woo_qty()
        return True
