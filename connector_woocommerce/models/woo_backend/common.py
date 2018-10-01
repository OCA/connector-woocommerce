# © 2009 Tech-Receptives Solutions Pvt. Ltd.
# © 2018 Serpent Consulting Services Pvt. Ltd.
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
# See LICENSE file for full copyright and licensing details.

import logging
from contextlib import contextmanager
from datetime import datetime

from odoo import models, api, fields, _
from odoo.addons.connector.models import checkpoint
from odoo.exceptions import Warning

from ...components.backend_adapter import WooLocation, WooAPI

_logger = logging.getLogger(__name__)

try:
    from woocommerce import API
except ImportError:
    _logger.debug("Cannot import 'woocommerce'")


class WooBackend(models.Model):
    _name = 'woo.backend'
    _inherit = 'connector.backend'
    _description = 'WooCommerce Backend Configuration'

    name = fields.Char(string='name')
    location = fields.Char("Url")
    consumer_key = fields.Char("Consumer key")
    consumer_secret = fields.Char("Consumer Secret")
    version = fields.Selection([
        ('v2', 'V2'),
        ('v3', 'V3')
    ],
        string='Version')
    verify_ssl = fields.Boolean("Verify SSL")
    default_lang_id = fields.Many2one(
        comodel_name='res.lang',
        string='Default Language',
        help="If a default language is selected, the records "
             "will be imported in the translation of this language.\n"
             "Note that a similar configuration exists "
             "for each storeview.",
    )

    @contextmanager
    @api.multi
    def work_on(self, model_name, **kwargs):
        self.ensure_one()
        lang = self.default_lang_id
        if lang.code != self.env.context.get('lang'):
            self = self.with_context(lang=lang.code)
        woo_location = WooLocation(
            self.location,
            self.consumer_key,
            self.consumer_secret,
            self.version or 'v3'
        )
        with WooAPI(woo_location) as woo_api:
            _super = super(WooBackend, self)
            # from the components we'll be able to do: self.work.woo_api
            with _super.work_on(
                    model_name, woo_api=woo_api, **kwargs) as work:
                yield work

    @api.multi
    def add_checkpoint(self, record):
        self.ensure_one()
        record.ensure_one()
        return checkpoint.add_checkpoint(self.env, record._name, record.id,
                                         self._name, self.id)

    @api.multi
    def update_existing_order(self, woo_sale_order, data):
        """ Enter Your logic for Existing Sale Order """
        return True

    @api.multi
    def check_existing_order(self, data):
        order_ids = []
        for val in data['orders']:
            woo_sale_order = self.env['woo.sale.order'].search(
                [('external_id', '=', val['id'])])
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
        version = self.version or 'v3'
        msg = str()
        try:
            wcapi = API(
                url=location,  # Your store URL
                consumer_key=cons_key,  # Your consumer key
                consumer_secret=sec_key,  # Your consumer secret
                version=version,  # WooCommerce WP REST API version
                query_string_auth=True  # Force Basic Authentication as query
                # string true and using under HTTPS
            )
            r = wcapi.get("products")
            if r.status_code == 404:
                msg = "(Enter Valid url)"
            val = r.json()
        except Exception as e:
            raise Warning(_(
                "Sorry, Could not reach WooCommerce site! %s %s") % (msg, e))
        msg = ''
        if 'errors' in r.json():
            msg = val['errors'][0]['message'] + '\n' + val['errors'][0]['code']
            raise Warning(_(msg))
        else:
            raise Warning(_('Test Success'))
        return True

    @api.multi
    def import_shippingzone(self):
        import_start_time = datetime.now()
        backend = self
        from_date = None
        self.env['woo.shipping.zone'].with_delay(priority=1).import_batch(
            backend,
            filters={'from_date': from_date,
                     'to_date': import_start_time},
        )
        return True

    @api.multi
    def import_category(self):
        import_start_time = datetime.now()
        backend = self
        from_date = None
        self.env['woo.product.category'].with_delay(priority=1).import_batch(
            backend,
            filters={'from_date': from_date,
                     'to_date': import_start_time},
        )
        return True

    @api.multi
    def import_product(self):
        import_start_time = datetime.now()
        backend = self
        from_date = None
        self.env['woo.product.product'].with_delay(priority=2).import_batch(
            backend,
            filters={'from_date': from_date,
                     'to_date': import_start_time},
        )
        return True

    @api.multi
    def import_customer(self):
        import_start_time = datetime.now()
        backend = self
        from_date = None
        self.env['woo.res.partner'].with_delay(priority=3).import_batch(
            backend,
            filters={'from_date': from_date,
                     'to_date': import_start_time}
        )
        return True

    @api.multi
    def import_order(self):
        import_start_time = datetime.now()
        backend = self
        from_date = None
        self.env['woo.sale.order'].with_delay(priority=4).import_batch(
            backend,
            filters={'from_date': from_date,
                     'to_date': import_start_time}
        )
        return True

    @api.multi
    def import_categories(self):
        """ Import Product categories from WooCommerce site """
        for backend in self:
            backend.import_category()
        return True

    @api.multi
    def import_products(self):
        """ Import Products from WooCommerce  site """
        for backend in self:
            backend.import_product()
        return True

    @api.multi
    def import_customers(self):
        """ Import Customers from WooCommerce  site """
        for backend in self:
            backend.import_customer()
        return True

    @api.multi
    def import_orders(self):
        """ Import Orders from WooCommerce  site """
        for backend in self:
            backend.import_order()
        return True

    @api.multi
    def export_data(self, model, domain=None):
        """
        This method create/updates the records with Odoo record
         on WooCoomerce store.
        """
        # Set active_field based on model for passing context purpose
        if model == 'res.country':
            active_field = 'res_country'
        elif model == 'sale.order':
            active_field = 'order_ids'
        elif model == 'res.partner':
            active_field = 'partner_ids'
        elif model == 'product.product':
            active_field = 'product_ids'
        elif model == 'product.category':
            active_field = 'product_cate_ids'

        self.ensure_one()
        if model == 'res.country':
            woo_obj = self.env["woo.shipping.zone"]
        else:
            woo_obj = self.env["woo.%s" % model]

        target_obj = self.env[model]
        import_ids = target_obj.search(domain)
        if not import_ids:
            raise Warning(_("Sorry, There is no record to Export!"))
        # Creating Jobs
        for import_id in import_ids:
            is_woo_data = woo_obj.search([
                ('odoo_id', '=', import_id.id)], limit=1)
            if is_woo_data:
                result = self.env['wizard.woo.export'].before_woo_validate(
                    active_field=active_field, active_model=model,
                    is_woo_data=is_woo_data, active_id=import_id)
                if not result:
                    context = {
                        'is_woo_data': is_woo_data.id,
                        'active_field': active_field,
                        'active_model': model,
                        'odoo_id': is_woo_data.odoo_id.id,
                        'external_id': is_woo_data.external_id,
                        'backend_id': import_id.woo_backend_id.id,
                    }
                    self.env['wizard.woo.validation'].with_context(
                        context).woo_validate()
                is_woo_data.with_delay().export_record()
            else:
                # Build environment to export
                import_id = woo_obj.create({
                    'backend_id': self.id,
                    'odoo_id': import_id.id,
                })
                # Do export
                import_id.with_delay().export_record()
        return True

    @api.multi
    def export_category(self):
        """
            This Method create/update the product category records
            on WooCommerce with Odoo data.
        """
        # Add filters if any here.
        domain = []
        context = self.env.context
        # Set domain based on context (Export/Update record condition)
        if context.get('export_product_category') and not context.get(
                'update_product_category'):
            domain = [('sync_data', '!=', True)]
        elif not context.get('export_product_category') and context.get(
                'update_product_category'):
            domain = [('sync_data', '=', True)]
        self.with_context(context).export_data("product.category", domain)

    @api.multi
    def export_product(self):
        """
            This Method create/update the product records
            on WooCommerce with Odoo data.
        """
        # Add filters if any here.
        domain = []
        context = self.env.context
        # Set domain based on context (Export/Update record condition)
        if context.get('export_product') and not context.get(
                'update_product'):
            domain = [('sync_data', '!=', True), ('active', '=', True)]
        elif not context.get('export_product') and context.get(
                'update_product'):
            domain = [('sync_data', '=', True), ('active', '=', True)]
        self.with_context(context).export_data("product.product", domain)

    @api.multi
    def export_customer(self):
        """
            This Method create/update the customer records
            on WooCommerce with Odoo data.
        """
        # Add filters if any here.
        domain = []
        context = self.env.context
        # Set domain based on context (Export/Update record condition)
        if context.get('export_customer') and not context.get(
                'update_customer'):
            domain = [('sync_data', '!=', True), ('customer', '=', True),
                      ('active', '=', True)]
        elif not context.get('export_customer')and context.get(
                'update_customer'):
            domain = [('sync_data', '=', True), ('customer', '=', True),
                      ('active', '=', True)]
        self.with_context(context).export_data("res.partner", domain)

    @api.multi
    def export_saleorder(self):
        """
            This Method create/update the customer records
            on WooCommerce with Odoo data.
        """
        # Add filters if any here.
        domain = []
        context = self.env.context
        # Set domain based on context (Export/Update record condition)
        if context.get('export_sale_order') and not context.get(
                'update_sale_order'):
            domain = [('sync_data', '!=', True)]
        elif not context.get('export_sale_order') and context.get(
                'update_sale_order'):
            domain = [('sync_data', '=', True)]
        self.with_context(context).export_data("sale.order", domain)

    @api.multi
    def export_shippingzone(self):
        """
            This Method create/update the customer records
            on WooCommerce with Odoo data.
        """
        # Add filters if any here.
        domain = []
        context = self.env.context
        # Set domain based on context (Export/Update record condition)
        if context.get('export_shippingzone') and not context.get(
                'update_shippingzone'):
            domain = [('sync_data', '!=', True)]
        elif not context.get('export_shippingzone') and context.get(
                'update_shippingzone'):
            domain = [('sync_data', '=', True)]
        self.with_context(context).export_data("res.country", domain)
