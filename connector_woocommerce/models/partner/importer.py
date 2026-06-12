# Copyright 2009 Tech-Receptives Solutions Pvt. Ltd.
# Copyright 2018 FactorLibre
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
import logging

from odoo.addons.component.core import Component
from odoo.addons.connector.components.mapper import mapping

_logger = logging.getLogger(__name__)


class CustomerBatchImporter(Component):
    """Import the WooCommerce Partners.

    For every partner in the list, a delayed job is created.
    """

    _name = "woocommerce.partner.batch.importer"
    _inherit = "woocommerce.delayed.batch.importer"
    _apply_on = "woo.res.partner"

    def run(self, filters=None):
        """Run the synchronization"""
        from_date = filters.pop("from_date", None)
        to_date = filters.pop("to_date", None)
        record_ids = self.backend_adapter.search(
            filters,
            from_date=from_date,
            to_date=to_date,
        )
        _logger.info("search for woo partners %s returned %s", filters, record_ids)
        for record_id in record_ids:
            self._import_record(record_id)


class CustomerImporter(Component):
    _name = "woocommerce.partner.importer"
    _inherit = "woocommerce.importer"
    _apply_on = "woo.res.partner"


class CustomerImportMapper(Component):
    _name = "woocommerce.partner.import.mapper"
    _inherit = "woocommerce.import.mapper"
    _apply_on = "woo.res.partner"

    direct = [
        ("email", "email"),
    ]

    @mapping
    def name(self, record):
        return {"name": record["first_name"] + " " + record["last_name"]}

    @mapping
    def city(self, record):
        if record.get("billing_address"):
            rec = record["billing_address"]
            return {"city": rec["city"] or None}

    @mapping
    def zip(self, record):
        if record.get("billing_address"):
            rec = record["customer"]["billing_address"]
            return {"zip": rec["postcode"] or None}

    @mapping
    def address(self, record):
        if record.get("billing_address"):
            rec = record["billing_address"]
            return {"street": rec["address_1"] or None}

    @mapping
    def address_2(self, record):
        if record.get("billing_address"):
            rec = record["billing_address"]
            return {"street2": rec["address_2"] or None}

    @mapping
    def country(self, record):
        if record.get("billing_address"):
            rec = record["billing_address"]
            if rec["country"]:
                country_id = self.env["res.country"].search(
                    [("code", "=", rec["country"])]
                )
                country_id = country_id.id
            else:
                country_id = False
            return {"country_id": country_id}

    @mapping
    def state(self, record):
        if record.get("billing_address"):
            rec = record["billing_address"]
            if rec["state"] and rec["country"]:
                state_id = self.env["res.country.state"].search(
                    [("code", "=", rec["state"])]
                )
                if not state_id:
                    country_id = self.env["res.country"].search(
                        [("code", "=", rec["country"])]
                    )
                    state_id = self.env["res.country.state"].create(
                        {
                            "name": rec["state"],
                            "code": rec["state"],
                            "country_id": country_id.id,
                        }
                    )
                state_id = state_id.id or False
            else:
                state_id = False
            return {"state_id": state_id}

    @mapping
    def backend_id(self, record):
        return {"backend_id": self.backend_record.id}
