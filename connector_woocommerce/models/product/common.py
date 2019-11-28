# © 2009 Tech-Receptives Solutions Pvt. Ltd.
# © 2018 FactorLibre
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging

from odoo import models, fields
from odoo.addons.component.core import Component

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
        comodel_name='wc.backend',
        string='Woo Backend',
        store=True,
        readonly=False,
        required=True,
    )

    slug = fields.Char('Slug Name')
    credated_at = fields.Date('created_at')
    weight = fields.Float('weight')


class ProductProductAdapter(Component):
    _name = 'woocommerce.product.product.adapter'
    _inherit = 'woocommerce.adapter'
    _apply_on = 'woo.product.product'

    _woo_model = 'products'

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
        products = self._call('products',
                              [filters] if filters else [{}])
        return [product['id'] for product in products]
