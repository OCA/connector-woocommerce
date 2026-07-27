# Copyright 2009 Tech-Receptives Solutions Pvt. Ltd.
# Copyright 2018 FactorLibre
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
import logging
from contextlib import contextmanager

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ...components.backend_adapter import WooAPI, WooLocation

_logger = logging.getLogger(__name__)

IMPORT_DELTA_BUFFER = 30  # seconds


class WooBackend(models.Model):
    _name = "wc.backend"
    _inherit = "connector.backend"
    _description = "WooCommerce Backend Configuration"

    @api.model
    def select_versions(self):
        """Available versions in the backend.

        Can be inherited to add custom versions.  Using this method
        to add a version from an ``_inherit`` does not constrain
        to redefine the ``version`` field in the ``_inherit`` model.
        """
        return [("v2", "V2")]

    name = fields.Char(
        required=True,
    )
    active = fields.Boolean(default=True)
    location = fields.Char(
        string="Url",
        required=True,
    )
    consumer_key = fields.Char()
    consumer_secret = fields.Char()
    version = fields.Selection(
        selection="select_versions",
        required=True,
    )
    verify_ssl = fields.Boolean(
        string="Verify SSL",
    )
    warehouse_id = fields.Many2one(
        comodel_name="stock.warehouse",
        string="Warehouse",
        required=True,
        help="Warehouse used to compute the stock quantities.",
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        related="warehouse_id.company_id",
        string="Company",
        readonly=True,
    )
    default_lang_id = fields.Many2one(
        comodel_name="res.lang",
        string="Default Language",
        help="If a default language is selected, the records "
        "will be imported in the translation of this language.\n"
        "Note that a similar configuration exists "
        "for each storeview.",
    )

    @contextmanager
    def work_on(self, model_name, **kwargs):
        self.ensure_one()
        # lang = self.default_lang_id
        # if lang.code != self.env.context.get("lang"):
        #     self = self.with_context(lang=lang.code)
        woocommerce_location = WooLocation(
            self.location,
            self.consumer_key,
            self.consumer_secret,
            verify_ssl=self.verify_ssl,
        )
        # TODO: Check Auth Basic
        # if self.use_auth_basic:
        #     magento_location.use_auth_basic = True
        #     magento_location.auth_basic_username = self.auth_basic_username
        #     magento_location.auth_basic_password = self.auth_basic_password
        wc_api = WooAPI(woocommerce_location)
        _super = super()
        with _super.work_on(model_name, wc_api=wc_api, **kwargs) as work:
            yield work

    def get_product_ids(self, data):
        product_ids = [x["id"] for x in data["products"]]
        product_ids = sorted(product_ids)
        return product_ids

    def get_product_category_ids(self, data):
        product_category_ids = [x["id"] for x in data["product_categories"]]
        product_category_ids = sorted(product_category_ids)
        return product_category_ids

    def get_customer_ids(self, data):
        customer_ids = [x["id"] for x in data["customers"]]
        customer_ids = sorted(customer_ids)
        return customer_ids

    def get_order_ids(self, data):
        order_ids = self.check_existing_order(data)
        return order_ids

    def update_existing_order(self, woo_sale_order, data):
        """Enter Your logic for Existing Sale Order"""
        return True

    def check_existing_order(self, data):
        order_ids = []
        for val in data["orders"]:
            woo_sale_order = self.env["woo.sale.order"].search(
                [("external_id", "=", val["id"])]
            )
            if woo_sale_order:
                self.update_existing_order(woo_sale_order[0], val)
                continue
            order_ids.append(val["id"])
        return order_ids

    def test_connection(self):
        """Check the credentials against the store.

        Uses the same client the importers use, so that a passing test really
        means the imports will authenticate. Building a separate client here
        made it possible for this to succeed while every import failed.
        """
        self.ensure_one()
        response = WooAPI(
            WooLocation(
                self.location,
                self.consumer_key,
                self.consumer_secret,
                verify_ssl=self.verify_ssl,
            )
        ).api.get("products")

        if response.status_code == 404:
            raise UserError(_("Enter Valid url"))

        payload = response.json()
        if not response.ok or "errors" in payload:
            if "errors" in payload:
                error = payload["errors"][0]
                detail = "{}\n{}".format(error["message"], error["code"])
            else:
                detail = "{} - {}".format(
                    payload.get("code", response.status_code),
                    payload.get("message", response.reason),
                )
            raise UserError(_("Could not connect to WooCommerce:\n%s") % detail)

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "type": "success",
                "title": _("Connection successful"),
                "message": _("Odoo can reach %s and the credentials are valid.")
                % self.location,
                "sticky": False,
            },
        }

    def import_categories(self):
        for backend in self:
            self.env["woo.product.category"].with_delay().import_batch(backend)
        return True

    def import_products(self):
        for backend in self:
            self.env["woo.product.product"].with_delay().import_batch(backend)
        return True

    def import_customers(self):
        for backend in self:
            self.env["woo.res.partner"].with_delay().import_batch(backend)
        return True

    def import_orders(self):
        for backend in self:
            self.env["woo.sale.order"].with_delay().import_batch(backend)
        return True

    # @api.multi
    # def import_order(self):
    #     session = ConnectorSession(self.env.cr, self.env.uid,
    #                                context=self.env.context)
    #     import_start_time = datetime.now()
    #     backend_id = self.id
    #     from_date = None
    #     sale_order_import_batch.delay(
    #         session, "woo.sale.order", backend_id,
    #         {"from_date": from_date,
    #          "to_date": import_start_time}, priority=4)
    #     return True

    # @api.multi
    # def import_categories(self):
    #     """ Import Product categories """
    #     for backend in self:
    #         backend.import_category()
    #     return True

    # @api.multi
    # def import_products(self):
    #     """ Import categories from all websites """
    #     for backend in self:
    #         backend.import_product()
    #     return True

    # @api.multi
    # def import_orders(self):
    #     """ Import Orders from all websites """
    #     for backend in self:
    #         backend.import_order()
    #     return True
