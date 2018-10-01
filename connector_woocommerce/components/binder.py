# © 2009 Tech-Receptives Solutions Pvt. Ltd.
# © 2018 Serpent Consulting Services Pvt. Ltd.
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
# See LICENSE file for full copyright and licensing details.

from odoo.addons.component.core import Component


class WooModelBinder(Component):
    """ Bind records and give odoo/woo ids correspondence

    Binding models are models called ``woo.{normal_model}``,
    like ``woo.res.partner`` or ``woo.product.product``.
    They are ``_inherits`` of the normal models and contains
    the Woo ID, the ID of the Woo Backend and the additional
    fields belonging to the Woo instance.
    """
    _name = 'woo.binder'
    _inherit = ['base.binder', 'base.woo.connector']
    _apply_on = [
        'woo.res.partner',
        'woo.product.category',
        'woo.product.product',
        'woo.sale.order',
        'woo.sale.order.line',
        'woo.shipping.zone',
    ]
