# © 2009 Tech-Receptives Solutions Pvt. Ltd.
# © 2018 Serpent Consulting Services Pvt. Ltd.
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
# See LICENSE file for full copyright and licensing details.

import logging

import xmlrpc.client
from odoo import models, fields, api
from odoo.addons.component.core import Component
from odoo.addons.connector.exception import IDMissingInBackend
from odoo.addons.queue_job.job import job, related_action

_logger = logging.getLogger(__name__)


class WooProductProduct(models.Model):
    _name = 'woo.product.product'
    _inherit = 'woo.binding'
    _inherits = {'product.product': 'odoo_id'}
    _description = 'woo product product'
    _rec_name = 'name'

    odoo_id = fields.Many2one(comodel_name='product.product',
                              string='product',
                              required=True,
                              ondelete='cascade')
    backend_id = fields.Many2one(
        comodel_name='woo.backend',
        string='Woo Backend',
        store=True,
        readonly=False,
        required=True,
    )
    slug = fields.Char('Slung Name')
    credated_at = fields.Date('created_at')
    weight = fields.Float('weight')

    @job(default_channel='root.woo')
    @related_action(action='related_action_unwrap_binding')
    @api.multi
    def export_record(self):
        """ Export Products. """
        for rec in self:
            rec.ensure_one()
            with rec.backend_id.work_on(rec._name) as work:
                exporter = work.component(usage='product.product.exporter')
                return exporter.run(self)


class ProductProduct(models.Model):
    _inherit = 'product.product'

    woo_categ_ids = fields.Many2many(
        comodel_name='product.category',
        string='Woo product category',
    )
    in_stock = fields.Boolean('In Stock')
    woo_bind_ids = fields.One2many(
        comodel_name='woo.product.product',
        inverse_name='odoo_id',
        string="Woo Bindings",
    )
    # These fields are required for export
    sync_data = fields.Boolean("Synch with Woo?")
    woo_backend_id = fields.Many2one(
        'woo.backend',
        string="WooCommerce Store"
    )


class ProductProductAdapter(Component):
    _name = 'woo.product.product.adapter'
    _inherit = 'woo.adapter'
    _apply_on = 'woo.product.product'

    _woo_model = 'products'
    _woo_base_model = 'products'

    def _call(self, method, resource, arguments):
        try:
            return super(ProductProductAdapter, self)._call(
                method,
                resource,
                arguments
            )
        except xmlrpc.client.Fault as err:
            # this is the error in the WooCommerce API
            # when the customer does not exist
            if err.faultCode == 102:
                raise IDMissingInBackend
            else:
                raise

    def search(self, method=None, filters=None, from_date=None, to_date=None):
        """ Search records according to some criteria and return a
        list of ids

        :rtype: list
        """
        WOO_DATETIME_FORMAT = '%Y/%m/%d %H:%M:%S'
        dt_fmt = WOO_DATETIME_FORMAT
        if from_date is not None:
            # updated_at include the created records
            filters.setdefault('updated_at', {})
            filters['updated_at']['from'] = from_date.strftime(dt_fmt)
        if to_date is not None:
            filters.setdefault('updated_at', {})
            filters['updated_at']['to'] = to_date.strftime(dt_fmt)
        res = self._call(method, 'products', [filters] if filters else [{}])
        # Set product ids and return it(Due to new WooCommerce REST API)
        product_ids = list()
        for product in res.get('products'):
            product_ids.append(product.get('id'))
        return product_ids

    def get_images(self, id, method='get'):
        return self._call(
            method,
            'products/' + str(id),
            []
        )

    def create(self, data):
        """ Create a record on the external system """
        data = {
            "product": data
        }
        return self._call('post', self._woo_base_model, data)

    def write(self, id, data):
        """ Update records on the external system """
        data = {
            "product": data
        }
        return self._call('put', self._woo_base_model + "/" + str(id), data)

    def is_woo_record(self, woo_id, filters=None):
        """
        This method is verify the existing record on WooCommerce.
        @param: woo_id : External id (int)
        @param: filters : Filters to check (json)
        @return: result : Response of Woocom (Boolean)
        """
        self._call(
            'get',
            self._woo_base_model + '/' + str(woo_id),
            filters
        )
        return True
