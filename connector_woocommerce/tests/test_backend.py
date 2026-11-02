# Copyright 2024 David Palanca (Grupo Isonor) - www.grupoisonor.es
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from unittest import mock

from odoo.exceptions import UserError

from odoo.addons.queue_job.tests.common import trap_jobs

from .common import BACKEND_API_PATH, WooTestCase


class TestWooBackend(WooTestCase):
    """Unit tests for the ``wc.backend`` model (no network access)."""

    def test_select_versions(self):
        self.assertIn(("v2", "V2"), self.backend.select_versions())

    def test_get_product_ids_sorted(self):
        data = {"products": [{"id": 3}, {"id": 1}, {"id": 2}]}
        self.assertEqual(self.backend.get_product_ids(data), [1, 2, 3])

    def test_get_product_category_ids_sorted(self):
        data = {"product_categories": [{"id": 5}, {"id": 2}]}
        self.assertEqual(self.backend.get_product_category_ids(data), [2, 5])

    def test_get_customer_ids_sorted(self):
        data = {"customers": [{"id": 9}, {"id": 4}]}
        self.assertEqual(self.backend.get_customer_ids(data), [4, 9])

    def test_get_order_ids_without_existing(self):
        data = {"orders": [{"id": 7}, {"id": 8}]}
        self.assertEqual(self.backend.get_order_ids(data), [7, 8])

    def test_check_existing_order_skips_imported(self):
        partner = self.env["res.partner"].create({"name": "Woo Client"})
        self.env["woo.sale.order"].create(
            {
                "backend_id": self.backend.id,
                "external_id": "7",
                "partner_id": partner.id,
            }
        )
        data = {"orders": [{"id": 7}, {"id": 8}]}
        with mock.patch.object(
            type(self.backend), "update_existing_order", return_value=True
        ) as updater:
            order_ids = self.backend.check_existing_order(data)
        # The already imported order (7) is skipped and updated instead.
        self.assertEqual(order_ids, [8])
        updater.assert_called_once()

    def test_update_existing_order_returns_true(self):
        order = self.env["woo.sale.order"]
        self.assertTrue(self.backend.update_existing_order(order, {}))

    def test_test_connection_invalid_url(self):
        response = mock.Mock()
        response.status_code = 404
        with mock.patch(BACKEND_API_PATH) as api_cls:
            api_cls.return_value.get.return_value = response
            with self.assertRaisesRegex(UserError, "Enter Valid url"):
                self.backend.test_connection()

    def test_test_connection_api_errors(self):
        response = mock.Mock()
        response.status_code = 200
        response.json.return_value = {
            "errors": [{"message": "Bad credentials", "code": "woocommerce_rest"}]
        }
        with mock.patch(BACKEND_API_PATH) as api_cls:
            api_cls.return_value.get.return_value = response
            with self.assertRaisesRegex(UserError, "Bad credentials"):
                self.backend.test_connection()

    def test_test_connection_success(self):
        response = mock.Mock()
        response.status_code = 200
        response.json.return_value = []
        with mock.patch(BACKEND_API_PATH) as api_cls:
            api_cls.return_value.get.return_value = response
            with self.assertRaisesRegex(UserError, "Test Success"):
                self.backend.test_connection()

    def test_import_categories_enqueues_batch(self):
        with trap_jobs() as trap:
            self.backend.import_categories()
        trap.assert_jobs_count(1)
        trap.assert_enqueued_job(
            self.env["woo.product.category"].import_batch,
            args=(self.backend,),
        )

    def test_import_customers_enqueues_batch(self):
        with trap_jobs() as trap:
            self.backend.import_customers()
        trap.assert_jobs_count(1)
        trap.assert_enqueued_job(
            self.env["woo.res.partner"].import_batch,
            args=(self.backend,),
        )

    def test_import_products_enqueues_batch(self):
        with trap_jobs() as trap:
            self.backend.import_products()
        trap.assert_jobs_count(1)
        trap.assert_enqueued_job(
            self.env["woo.product.product"].import_batch,
            args=(self.backend,),
        )

    def test_import_orders_enqueues_batch(self):
        with trap_jobs() as trap:
            self.backend.import_orders()
        trap.assert_jobs_count(1)
        trap.assert_enqueued_job(
            self.env["woo.sale.order"].import_batch,
            args=(self.backend,),
        )
