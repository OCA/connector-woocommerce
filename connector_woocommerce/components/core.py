# Copyright 2018 FactorLibre
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.addons.component.core import AbstractComponent


class BaseWoocommerceConnectorComponent(AbstractComponent):
    """Base Woocommerce Connector Component

    All components of this connector should inherit from it.

    """

    _name = "base.woocommerce.connector"
    _inherit = "base.connector"
    _collection = "wc.backend"
