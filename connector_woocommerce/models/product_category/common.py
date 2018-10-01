# © 2009 Tech-Receptives Solutions Pvt. Ltd.
# © 2018 Serpent Consulting Services Pvt. Ltd.
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
# See LICENSE file for full copyright and licensing details.

import logging

import xmlrpc.client
from odoo import api, fields, models
from odoo.addons.component.core import Component
from odoo.addons.connector.exception import IDMissingInBackend
from odoo.addons.queue_job.job import job, related_action

_logger = logging.getLogger(__name__)


class WooProductCategory(models.Model):
    _name = 'woo.product.category'
    _inherit = 'woo.binding'
    _inherits = {'product.category': 'odoo_id'}
    _description = 'Woo Product Category'

    _rec_name = 'name'

    odoo_id = fields.Many2one(
        'product.category',
        string='category',
        required=True,
        ondelete='cascade'
    )
    backend_id = fields.Many2one(
        comodel_name='woo.backend',
        string='Woo Backend',
        store=True,
        readonly=False,
    )
    slug = fields.Char('Slung Name')
    woo_parent_id = fields.Many2one(
        comodel_name='woo.product.category',
        string='Woo Parent Category',
        ondelete='cascade', )
    description = fields.Char('Description')
    count = fields.Integer('count')
    woo_child_ids = fields.One2many(
        comodel_name='woo.product.category',
        inverse_name='woo_parent_id',
        string='Woo Child Categories',
    )

    @job(default_channel='root.woo')
    @related_action(action='related_action_unwrap_binding')
    @api.multi
    def export_record(self):
        """ Export Product Category. """
        for rec in self:
            rec.ensure_one()
            with rec.backend_id.work_on(rec._name) as work:
                exporter = work.component(usage='product.category.exporter')
                return exporter.run(self)


class ProductCategory(models.Model):
    _inherit = 'product.category'

    woo_bind_ids = fields.One2many(
        comodel_name='woo.product.category',
        inverse_name='odoo_id',
        string="Woo Bindings",
    )
    woo_image = fields.Binary("WooCommerce Image")
    # These fields are required for export
    sync_data = fields.Boolean("Synch with Woo?")
    woo_backend_id = fields.Many2one(
        'woo.backend',
        string="WooCommerce Store"
    )


class CategoryAdapter(Component):
    _name = 'woo.product.category.adapter'
    _inherit = 'woo.adapter'
    _apply_on = 'woo.product.category'

    _woo_model = 'products/categories'

    def _call(self, method, resource, arguments):
        try:
            return super(CategoryAdapter, self)._call(method, resource,
                                                      arguments)
        except xmlrpc.client.Fault as err:
            # this is the error in the WooCommerce API
            # when the product Category does not exist
            if err.faultCode == 102:
                raise IDMissingInBackend
            else:
                raise

    def search(self, method, filters=None, from_date=None, to_date=None):
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
        res = self._call(method, 'products/categories',
                         [filters] if filters else [{}])
        # Set product category ids and return
        # it(Due to new WooCommerce REST API)
        cat_ids = list()
        for category in res.get('product_categories'):
            cat_ids.append(category.get('id'))
        return cat_ids

    def create(self, data):
        """ Create a record on the external system """
        data = {
            "product_category": data
        }
        return self._call('post', self._woo_model, data)

    def write(self, id, data):
        """ Update records on the external system """
        data = {
            "product_category": data
        }
        return self._call('put', self._woo_model + "/" + str(id), data)

    def is_woo_record(self, woo_id, filters=None):
        """
        This method is verify the existing record on WooCommerce.
        @param: woo_id : External id (int)
        @param: filters : Filters to check (json)
        @return: result : Response of Woocom (Boolean)
        """
        return self._call('get', self._woo_model + '/' + str(woo_id), filters)
