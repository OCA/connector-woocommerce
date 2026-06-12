# Copyright 2024 David Palanca (Grupo Isonor) - www.grupoisonor.es
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from unittest import mock

from odoo.addons.connector_woocommerce.components import backend_adapter
from odoo.addons.connector_woocommerce.components.backend_adapter import (
    WooAPI,
    WooLocation,
    call_to_key,
    record,
)

from .common import WooTestCase


class TestBackendAdapterHelpers(WooTestCase):
    """Unit tests for the pure helpers of ``backend_adapter``."""

    def test_call_to_key_is_hashable_and_deterministic(self):
        key_a = call_to_key("products", [{"a": 1, "b": [1, 2]}, 3])
        key_b = call_to_key("products", [{"b": [1, 2], "a": 1}, 3])
        # The key must be hashable (it is used as a dict key)...
        self.assertIsInstance(hash(key_a), int)
        # ...and independent from the dict key ordering.
        self.assertEqual(key_a, key_b)
        self.assertEqual(key_a[0], "products")

    def test_call_to_key_freezes_nested_structures(self):
        key = call_to_key("m", [{"a": [1, {"b": 2}]}])
        method, frozen_args = key
        self.assertEqual(method, "m")
        # The frozen argument must be hashable.
        self.assertIsInstance(hash(frozen_args), int)

    def test_record_stores_result_in_recorder(self):
        self.addCleanup(backend_adapter.recorder.clear)
        record("some/method", ["arg"], {"id": 99})
        key = call_to_key("some/method", ["arg"])
        self.assertEqual(backend_adapter.recorder[key], {"id": 99})

    def test_woo_location_exposes_location(self):
        location = WooLocation("https://shop.test", "ck", "cs")
        self.assertEqual(location.location, "https://shop.test")
        self.assertEqual(location.consumer_key, "ck")
        self.assertEqual(location.consumer_secret, "cs")

    def test_woo_api_builds_client_lazily(self):
        location = WooLocation("https://shop.test", "ck", "cs")
        woo_api = WooAPI(location)
        with mock.patch.object(backend_adapter, "API") as api_cls:
            client = woo_api.api
            # The client is built with the expected parameters...
            api_cls.assert_called_once_with(
                url="https://shop.test",
                consumer_key="ck",
                consumer_secret="cs",
                wp_api=True,
                version="wc/v3",
                query_string_auth=True,
            )
            self.assertIs(client, api_cls.return_value)
            self.assertTrue(client.is_ssl)
            # ...and cached: a second access does not build a new client.
            self.assertIs(woo_api.api, client)
            api_cls.assert_called_once()


class TestBackendAdapterComponents(WooTestCase):
    """Tests for the adapter components resolved through ``work_on``."""

    def test_work_on_provides_woo_api(self):
        with self.backend.work_on("woo.product.category") as work:
            self.assertIsInstance(work.wc_api, WooAPI)

    def test_generic_read_record(self):
        with (
            self.mock_api({"products/categories/5": {"id": 5}}) as mocked,
            self.backend.work_on("woo.product.category") as work,
        ):
            adapter = work.component(usage="backend.adapter")
            result = adapter.read_record(5)
        self.assertEqual(result, {"id": 5})
        mocked.assert_called_once_with("products/categories/5", [])

    def test_generic_search_read(self):
        with (
            self.mock_api({"products/categories.list": [{"id": 5}]}) as mocked,
            self.backend.work_on("woo.product.category") as work,
        ):
            adapter = work.component(usage="backend.adapter")
            result = adapter.search_read({})
        self.assertEqual(result, [{"id": 5}])
        mocked.assert_called_once_with("products/categories.list", [{}])

    def test_category_adapter_search_returns_ids(self):
        payload = [{"id": 11}, {"id": 7}, {"id": 9}]
        with (
            self.mock_api({"products/categories": payload}) as mocked,
            self.backend.work_on("woo.product.category") as work,
        ):
            adapter = work.component(usage="backend.adapter")
            result = adapter.search()
        self.assertEqual(result, [11, 7, 9])
        mocked.assert_called_once_with("products/categories", [{}])

    def test_customer_adapter_search_returns_ids(self):
        payload = [{"id": 1}, {"id": 2}]
        with (
            self.mock_api({"customers": payload}) as mocked,
            self.backend.work_on("woo.res.partner") as work,
        ):
            adapter = work.component(usage="backend.adapter")
            result = adapter.search()
        self.assertEqual(result, [1, 2])
        mocked.assert_called_once_with("customers", [{}])
