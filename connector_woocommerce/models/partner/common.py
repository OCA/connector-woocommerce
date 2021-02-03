# Copyright 2009 Tech-Receptives Solutions Pvt. Ltd.
# Copyright 2018 FactorLibre
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging
from odoo import models, fields
from odoo.addons.component.core import Component

from ...components.backend_adapter import WOO_DATETIME_FORMAT

_logger = logging.getLogger(__name__)


class WooResPartner(models.Model):
    _name = "woo.res.partner"
    _inherit = "woo.binding"
    _inherits = {"res.partner": "odoo_id"}
    _description = "woo res partner"

    _rec_name = "name"

    odoo_id = fields.Many2one(
        comodel_name="res.partner",
        string="Partner",
        required=True,
        ondelete="cascade",
    )
    backend_id = fields.Many2one(
        comodel_name="wc.backend",
        string="Woo Backend",
        store=True,
    )


class CustomerAdapter(Component):
    _name = "woocommerce.partner.adapter"
    _inherit = "woocommerce.adapter"
    _apply_on = "woo.res.partner"

    _woo_model = "customers"

    def search(self, filters=None, from_date=None, to_date=None):
        """ Search records according to some criteria and return a
        list of ids

        :rtype: list
        """
        if not filters:
            filters = {}
        dt_fmt = WOO_DATETIME_FORMAT
        if not from_date:
            # updated_at include the created records
            filters.setdefault("updated_at", {})
            filters["updated_at"]["from"] = from_date.strftime(dt_fmt)
        if not to_date:
            filters.setdefault("updated_at", {})
            filters["updated_at"]["to"] = to_date.strftime(dt_fmt)
        # the search method is on ol_customer instead of customer
        customers = self._call("customers", [filters] if filters else [{}])
        return [customer["id"] for customer in customers]
