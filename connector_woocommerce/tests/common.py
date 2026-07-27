# Copyright 2024 David Palanca (Grupo Isonor) - www.grupoisonor.es
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from contextlib import contextmanager
from unittest import mock

from odoo.addons.component.tests.common import TransactionComponentCase

API_CALL_PATH = (
    "odoo.addons.connector_woocommerce.components.backend_adapter.WooAPI.call"
)
BACKEND_API_PATH = "odoo.addons.connector_woocommerce.components.backend_adapter.API"


class WooTestCase(TransactionComponentCase):
    """Base test case for the WooCommerce connector.

    It creates a ready-to-use backend and provides helpers to mock the
    WooCommerce REST API so tests run completely offline.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.warehouse = cls.env.ref("stock.warehouse0")
        cls.backend = cls.env["wc.backend"].create(
            {
                "name": "Test Woo Backend",
                "location": "https://example.test",
                "consumer_key": "ck_testkey",
                "consumer_secret": "cs_testsecret",
                "version": "v2",
                "warehouse_id": cls.warehouse.id,
            }
        )

    @contextmanager
    def mock_api(self, responses):
        """Patch ``WooAPI.call`` so no real HTTP request is made.

        :param responses: either a ``dict`` mapping the called method string
            (e.g. ``"products/categories/10"``) to the payload to return, or a
            callable ``(method, arguments) -> payload``.
        """

        def _side_effect(method, arguments):
            if callable(responses):
                return responses(method, arguments)
            if method in responses:
                return responses[method]
            raise AssertionError(f"Unexpected WooCommerce API call: {method}")

        with mock.patch(API_CALL_PATH, side_effect=_side_effect) as mocked:
            yield mocked
