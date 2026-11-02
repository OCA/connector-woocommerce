# Copyright 2009 Tech-Receptives Solutions Pvt. Ltd.
# Copyright 2018 FactorLibre
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.addons.component.core import Component


class WooModelBinder(Component):
    """
    Bindings are done directly on the binding model.woo.product.category

    Binding models are models called ``woo.{normal_model}``,
    like ``woo.res.partner`` or ``woo.product.product``.
    They are ``_inherits`` of the normal models and contains
    the Woo ID, the ID of the Woo Backend and the additional
    fields belonging to the Woo instance.
    """

    _name = "woocommerce.binder"
    _inherit = ["base.binder", "base.woocommerce.connector"]
    _apply_on = [
        "woo.res.partner",
        "woo.product.category",
        "woo.product.product",
        "woo.sale.order",
        "woo.sale.order.line",
    ]
