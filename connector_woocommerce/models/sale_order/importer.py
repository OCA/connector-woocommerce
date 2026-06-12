# Copyright 2009 Tech-Receptives Solutions Pvt. Ltd.
# Copyright 2018 FactorLibre
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
import logging

from odoo.addons.component.core import Component
from odoo.addons.connector.components.mapper import mapping

_logger = logging.getLogger(__name__)


class SaleOrderBatchImporter(Component):
    """Import the WooCommerce Orders.

    For every order in the list, a delayed job is created.
    """

    _name = "woocommerce.sale.order.batch.importer"
    _inherit = "woocommerce.delayed.batch.importer"
    _apply_on = ["woo.sale.order"]

    def _import_record(self, external_id, job_options=None, **kwargs):
        job_options = {
            "max_retries": 0,
            "priority": 5,
        }
        return super()._import_record(external_id, job_options=job_options)

    def run(self, filters=None):
        """Run the synchronization"""
        from_date = filters.pop("from_date", None)
        to_date = filters.pop("to_date", None)
        record_ids = self.backend_adapter.search(
            filters,
            from_date=from_date,
            to_date=to_date,
        )
        _logger.info("search for woo orders %s returned %s", filters, record_ids)
        # Re-import every record: the importer updates the existing binding
        # idempotently when the order is already present, and creates it
        # otherwise. We never delete orders from Odoo on the WooCommerce side.
        for record_id in record_ids:
            self._import_record(record_id)


class SaleOrderImporter(Component):
    _name = "woocommerce.sale.order.importer"
    _inherit = "woocommerce.importer"
    _apply_on = ["woo.sale.order"]

    def _import_addresses(self):
        record = self.woo_record
        self._import_dependency(record["customer_id"], "woo.res.partner")

    def _import_dependencies(self):
        """Import the dependencies for the record"""
        record = self.woo_record

        self._import_addresses()
        record = record["items"]
        for line in record:
            _logger.debug("line: %s", line)
            if "product_id" in line:
                self._import_dependency(line["product_id"], "woo.product.product")

    def _clean_woo_items(self, resource):
        """
        Method that clean the sale order line given by WooCommerce before
        importing it

        This method has to stay here because it allow to customize the
        behavior of the sale order.

        """
        child_items = {}  # key is the parent item id
        top_items = []

        # Group the childs with their parent
        for item in resource["line_items"]:
            if item.get("parent_item_id"):
                child_items.setdefault(item["parent_item_id"], []).append(item)
            else:
                top_items.append(item)

        all_items = []
        for top_item in top_items:
            all_items.append(top_item)
        resource["items"] = all_items
        return resource

    def _get_woo_data(self):
        """Return the raw WooCommerce data for ``self.external_id``"""
        record = super()._get_woo_data()
        # sometimes we need to clean woo items (ex : configurable
        # product in a sale)
        record = self._clean_woo_items(record)
        return record


class SaleOrderImportMapper(Component):
    _name = "woocommerce.sale.order.mapper"
    _inherit = "woocommerce.import.mapper"
    _apply_on = "woo.sale.order"

    direct = [
        ("number", "name"),
    ]

    children = [("items", "woo_order_line_ids", "woo.sale.order.line")]

    @mapping
    def status(self, record):
        if record["status"]:
            status_id = self.env["woo.sale.order.status"].search(
                [("name", "=", record["status"])]
            )
            if status_id:
                return {"status_id": status_id[0].id}
            else:
                status_id = self.env["woo.sale.order.status"].create(
                    {"name": record["status"]}
                )
                return {"status_id": status_id.id}
        else:
            return {"status_id": False}

    @mapping
    def customer_id(self, record):
        binder = self.binder_for("woo.res.partner")
        partner = False
        if record.get("customer_id"):
            partner = binder.to_internal(record["customer_id"], unwrap=True) or False
        if not partner:
            partner = self._partner_from_billing(record.get("billing") or {})
        return {"partner_id": partner.id} if partner else {}

    def _partner_from_billing(self, billing):
        Partner = self.env["res.partner"]
        email = (billing.get("email") or "").strip()
        if email:
            existing = Partner.search([("email", "=ilike", email)], limit=1)
            if existing:
                return existing
        country_id = state_id = False
        if billing.get("country"):
            country = self.env["res.country"].search(
                [("code", "=", billing["country"])], limit=1
            )
            country_id = country.id
        if billing.get("state"):
            state = self.env["res.country.state"].search(
                [("code", "=", billing["state"])], limit=1
            )
            state_id = state.id
        name = (
            " ".join(
                p for p in [billing.get("first_name"), billing.get("last_name")] if p
            ).strip()
            or email
            or "WooCommerce Guest"
        )
        return Partner.create(
            {
                "name": name,
                "email": email or False,
                "street": billing.get("address_1") or False,
                "street2": billing.get("address_2") or False,
                "city": billing.get("city") or False,
                "phone": billing.get("phone") or False,
                "zip": billing.get("postcode") or False,
                "state_id": state_id,
                "country_id": country_id,
            }
        )

    @mapping
    def backend_id(self, record):
        return {"backend_id": self.backend_record.id}


class SaleOrderLineImportMapper(Component):
    _name = "woocommerce.sale.order.line.mapper"
    _inherit = "woocommerce.import.mapper"
    _apply_on = "woo.sale.order.line"

    direct = [
        ("quantity", "product_uom_qty"),
        ("price", "price_unit"),
    ]

    @mapping
    def name(self, record):
        return {"name": record.get("name") or "WC line"}

    @mapping
    def product_id(self, record):
        binder = self.binder_for("woo.product.product")
        product = binder.to_internal(record["product_id"], unwrap=True)
        assert product is not None, (
            f"product_id {record['product_id']} should have been imported in "
            "SaleOrderImporter._import_dependencies"
        )
        return {"product_id": product.id}
