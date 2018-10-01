# © 2009 Tech-Receptives Solutions Pvt. Ltd.
# © 2018 Serpent Consulting Services Pvt. Ltd.
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.addons.component.core import AbstractComponent


class BaseWooConnectorComponent(AbstractComponent):
    """ Base Woo Connector Component

    All components of this connector should inherit from it.
    """

    _name = 'base.woo.connector'
    _inherit = 'base.connector'
    _collection = 'woo.backend'
