# Copyright 2009 Tech-Receptives Solutions Pvt. Ltd.
# Copyright 2018 FactorLibre
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging

from odoo import models, fields, api
from odoo.addons.component.core import Component

_logger = logging.getLogger(__name__)


class WooSaleOrderStatus(models.Model):
    _name = "woo.sale.order.status"
    _description = "WooCommerce Sale Order Status"

    name = fields.Char()
    desc = fields.Text(
        string="Description",
    )


class WooSaleOrder(models.Model):
    _name = "woo.sale.order"
    _inherit = "woo.binding"
    _inherits = {"sale.order": "odoo_id"}
    _description = "Woo Sale Order"

    _rec_name = "name"

    status_id = fields.Many2one(
        comodel_name="woo.sale.order.status",
        string="WooCommerce Order Status",
    )
    odoo_id = fields.Many2one(
        comodel_name="sale.order",
        string="Sale Order",
        required=True,
        ondelete="cascade",
    )
    woo_order_line_ids = fields.One2many(
        comodel_name="woo.sale.order.line",
        inverse_name="woo_order_id",
        string="Woo Order Lines"
    )
    backend_id = fields.Many2one(
        comodel_name="wc.backend",
        string="Woo Backend",
        store=True,
        required=True,
    )


class WooSaleOrderLine(models.Model):
    _name = "woo.sale.order.line"
    _inherits = {"sale.order.line": "odoo_id"}
    _description = "Woo Sale Order Line"

    woo_order_id = fields.Many2one(
        comodel_name="woo.sale.order",
        string="Woo Sale Order",
        required=True,
        ondelete="cascade",
        index=True,
    )
    odoo_id = fields.Many2one(
        comodel_name="sale.order.line",
        string="Sale Order Line",
        required=True,
        ondelete="cascade",
    )
    backend_id = fields.Many2one(
        related="woo_order_id.backend_id",
        string="Woo Backend",
        readonly=True,
        store=True,
        required=False,
    )

    @api.model
    def create(self, values):
        woo_order_id = values["woo_order_id"]
        binding = self.env["woo.sale.order"].browse(woo_order_id)
        values["order_id"] = binding.odoo_id.id
        binding = super(WooSaleOrderLine, self).create(values)
        return binding


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    woo_bind_ids = fields.One2many(
        comodel_name="woo.sale.order.line",
        inverse_name="odoo_id",
        string="WooCommerce Bindings",
    )


class SaleOrderAdapter(Component):
    _name = "woocommerce.sale.order.adapater"
    _inherit = "woocommerce.adapter"
    _apply_on = "woo.sale.order"

    _woo_model = "orders"

    def search(self, filters=None, from_date=None, to_date=None):
        """ Search records according to some criteria and return a
        list of ids

        :rtype: list
        """
        if not filters:
            filters = {}
        WOO_DATETIME_FORMAT = "%Y/%m/%d %H:%M:%S"
        dt_fmt = WOO_DATETIME_FORMAT
        if not from_date:
            # updated_at include the created records
            filters.setdefault("updated_at", {})
            filters["updated_at"]["from"] = from_date.strftime(dt_fmt)
        if not to_date:
            filters.setdefault("updated_at", {})
            filters["updated_at"]["to"] = to_date.strftime(dt_fmt)
        orders = self._call("orders",
                            [filters] if filters else [{}])
        return [order["id"] for order in orders]
