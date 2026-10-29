# Copyright 2009 Tech-Receptives Solutions Pvt. Ltd.
# Copyright 2018 FactorLibre
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging

from odoo import fields, models

from odoo.addons.component.core import Component

from ...components.backend_adapter import WOO_DATETIME_FORMAT

_logger = logging.getLogger(__name__)


class WooProductProduct(models.Model):
    _name = "woo.product.product"
    _inherit = "woo.binding"
    _inherits = {"product.product": "odoo_id"}
    _description = "woo product product"

    _rec_name = "name"

    odoo_id = fields.Many2one(
        comodel_name="product.product",
        string="product",
        required=True,
        ondelete="cascade",
    )
    backend_id = fields.Many2one(
        comodel_name="wc.backend",
        string="Woo Backend",
        store=True,
        required=True,
    )

    slug = fields.Char(
        string="Slug Name",
    )
    created_at = fields.Date()
    weight = fields.Float()


class ProductProductAdapter(Component):
    _name = "woocommerce.product.product.adapter"
    _inherit = "woocommerce.adapter"
    _apply_on = "woo.product.product"

    _woo_model = "products"

    def search(self, filters=None, from_date=None, to_date=None):
        """Search records according to some criteria and return a
        list of ids

        :rtype: list
        """
        if not filters:
            filters = {}
        dt_fmt = WOO_DATETIME_FORMAT
        if from_date:
            filters["modified_after"] = from_date.strftime(dt_fmt)
            filters["dates_are_gmt"] = True
        if to_date:
            filters["modified_before"] = to_date.strftime(dt_fmt)
            filters["dates_are_gmt"] = True
        products = self._call("products", filters or {})
        return [product["id"] for product in products]
