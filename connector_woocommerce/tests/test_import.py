# Copyright 2024 David Palanca (Grupo Isonor) - www.grupoisonor.es
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.addons.queue_job.tests.common import trap_jobs

from .common import WooTestCase


class TestImportCategory(WooTestCase):
    """Full import flow for product categories with a mocked API."""

    def _binding(self, external_id):
        return self.env["woo.product.category"].search(
            [
                ("backend_id", "=", self.backend.id),
                ("external_id", "=", external_id),
            ]
        )

    def test_import_record_creates_binding(self):
        payload = {
            "products/categories/10": {
                "id": 10,
                "name": "Shoes",
                "parent": 0,
                "slug": "shoes",
            }
        }
        with self.mock_api(payload):
            self.env["woo.product.category"].import_record(self.backend, "10")
        binding = self._binding("10")
        self.assertEqual(len(binding), 1)
        self.assertEqual(binding.odoo_id.name, "Shoes")
        self.assertEqual(binding.backend_id, self.backend)

    def test_import_record_is_idempotent(self):
        payload = {
            "products/categories/10": {
                "id": 10,
                "name": "Shoes",
                "parent": 0,
            }
        }
        with self.mock_api(payload):
            self.env["woo.product.category"].import_record(self.backend, "10")
            self.env["woo.product.category"].import_record(self.backend, "10")
        # The unique constraint (backend_id, external_id) must be respected.
        self.assertEqual(len(self._binding("10")), 1)

    def test_import_record_imports_parent_dependency(self):
        def dispatcher(method, arguments):
            data = {
                "products/categories/1": {"id": 1, "name": "Root", "parent": 0},
                "products/categories/2": {"id": 2, "name": "Child", "parent": 1},
            }
            return data[method]

        with self.mock_api(dispatcher):
            self.env["woo.product.category"].import_record(self.backend, "2")
        child = self._binding("2")
        parent = self._binding("1")
        self.assertEqual(len(parent), 1)
        self.assertEqual(child.odoo_id.parent_id, parent.odoo_id)
        self.assertEqual(child.woo_parent_id, parent)

    def test_import_batch_delays_and_performs_jobs(self):
        def dispatcher(method, arguments):
            data = {
                "products/categories": [{"id": 10}, {"id": 11}],
                "products/categories/10": {"id": 10, "name": "Shoes", "parent": 0},
                "products/categories/11": {"id": 11, "name": "Hats", "parent": 0},
            }
            return data[method]

        with self.mock_api(dispatcher):
            with trap_jobs() as trap:
                self.env["woo.product.category"].import_batch(self.backend, filters={})
                trap.assert_jobs_count(2)
                trap.perform_enqueued_jobs()
        self.assertEqual(len(self._binding("10")), 1)
        self.assertEqual(len(self._binding("11")), 1)


class TestImportPartner(WooTestCase):
    """Full import flow for customers with a mocked API."""

    def _binding(self, external_id):
        return self.env["woo.res.partner"].search(
            [
                ("backend_id", "=", self.backend.id),
                ("external_id", "=", external_id),
            ]
        )

    def test_import_record_creates_partner(self):
        payload = {
            "customers/5": {
                "id": 5,
                "first_name": "John",
                "last_name": "Doe",
                "email": "john@example.test",
            }
        }
        with self.mock_api(payload):
            self.env["woo.res.partner"].import_record(self.backend, "5")
        binding = self._binding("5")
        self.assertEqual(len(binding), 1)
        self.assertEqual(binding.odoo_id.name, "John Doe")
        self.assertEqual(binding.odoo_id.email, "john@example.test")

    def test_import_record_maps_billing_address(self):
        spain = self.env.ref("base.es")
        payload = {
            "customers/8": {
                "id": 8,
                "first_name": "Maria",
                "last_name": "Garcia",
                "email": "maria@example.test",
                "billing_address": {
                    "city": "Bilbao",
                    "postcode": "48001",
                    "address_1": "Gran Via 1",
                    "address_2": "3 B",
                    "country": "ES",
                    "state": "",
                },
            }
        }
        with self.mock_api(payload):
            self.env["woo.res.partner"].import_record(self.backend, "8")
        partner = self._binding("8").odoo_id
        self.assertEqual(partner.city, "Bilbao")
        self.assertEqual(partner.zip, "48001")
        self.assertEqual(partner.street, "Gran Via 1")
        self.assertEqual(partner.street2, "3 B")
        self.assertEqual(partner.country_id, spain)

    def test_import_batch_delays_and_performs_jobs(self):
        def dispatcher(method, arguments):
            data = {
                "customers": [{"id": 5}, {"id": 6}],
                "customers/5": {
                    "id": 5,
                    "first_name": "John",
                    "last_name": "Doe",
                    "email": "john@example.test",
                },
                "customers/6": {
                    "id": 6,
                    "first_name": "Jane",
                    "last_name": "Roe",
                    "email": "jane@example.test",
                },
            }
            return data[method]

        with self.mock_api(dispatcher):
            with trap_jobs() as trap:
                self.env["woo.res.partner"].import_batch(self.backend, filters={})
                trap.assert_jobs_count(2)
                trap.perform_enqueued_jobs()
        self.assertEqual(len(self._binding("5")), 1)
        self.assertEqual(len(self._binding("6")), 1)
