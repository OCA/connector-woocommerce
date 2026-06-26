# Copyright 2009 Tech-Receptives Solutions Pvt. Ltd.
# Copyright 2018 FactorLibre
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
import logging
import socket
import xmlrpc.client
from datetime import datetime

from odoo.addons.component.core import AbstractComponent
from odoo.addons.connector.exception import NetworkRetryableError, RetryableJobError
from odoo.addons.queue_job.exception import FailedJobError

_logger = logging.getLogger(__name__)

try:
    from woocommerce import API
except ImportError:
    _logger.debug("cannot import 'woocommerce'")

recorder = {}

WOO_DATETIME_FORMAT = "%Y/%m/%d %H:%M:%S"


def call_to_key(method, arguments):
    """Used to "freeze" the method and arguments of a call to WooCommerce
    so they can be hashable; they will be stored in a dict.

    Used in both the recorder and the tests.
    """

    def freeze(arg):
        if isinstance(arg, dict):
            items = dict((key, freeze(value)) for key, value in arg.items())
            return frozenset(iter(items.items()))
        elif isinstance(arg, list):
            return tuple([freeze(item) for item in arg])
        else:
            return arg

    new_args = []
    for arg in arguments:
        new_args.append(freeze(arg))
    return (method, tuple(new_args))


def record(method, arguments, result):
    """Utility function which can be used to record test data
    during synchronisations. Call it from WooCRUDAdapter._call

    Then ``output_recorder`` can be used to write the data recorded
    to a file.
    """
    recorder[call_to_key(method, arguments)] = result


def output_recorder(filename):
    import pprint

    with open(filename, "w") as f:
        pprint.pprint(recorder, f)
    _logger.debug("recorder written to file %s", filename)


class WooLocation:
    def __init__(self, location, consumer_key, consumer_secret):
        self._location = location
        self.consumer_key = consumer_key
        self.consumer_secret = consumer_secret

    @property
    def location(self):
        location = self._location
        return location


class WooAPI:
    def __init__(self, location):
        """
        :param location: Woocommerce Location
        :type location: :class:`WooLocation`
        """
        self._location = location
        self._api = None

    @property
    def api(self):
        if not self._api:
            api = API(
                url=self._location.location,
                consumer_key=self._location.consumer_key,
                consumer_secret=self._location.consumer_secret,
                wp_api=True,
                version="wc/v3",
                query_string_auth=True,
            )
            # Force basic-via-querystring even on plain HTTP (OAuth1 breaks
            # behind reverse proxies and dev containers).
            api.is_ssl = True
            self._api = api
        return self._api

    def call(self, method, arguments):
        try:
            if isinstance(arguments, list):
                while arguments and arguments[-1] is None:
                    arguments.pop()
            start = datetime.now()
            try:
                response = self.api.get(method)
                response_json = response.json()
                if not response.ok:
                    if response_json.get("code") and response_json.get("message"):
                        raise FailedJobError(
                            "{} error: {} - {}".format(
                                response.status_code,
                                response_json["code"],
                                response_json["message"],
                            )
                        )
                    else:
                        return response.raise_for_status()
                result = response_json
            except Exception:
                _logger.error("api.call(%s, %s) failed", method, arguments)
                raise
            else:
                _logger.debug(
                    "api.call(%s, %s) returned %s in %s seconds",
                    method,
                    arguments,
                    result,
                    (datetime.now() - start).seconds,
                )
            return result
        except (TimeoutError, OSError, socket.gaierror) as err:
            raise NetworkRetryableError(
                f"A network error caused the failure of the job: {err}"
            ) from err
        except xmlrpc.client.ProtocolError as err:
            if err.errcode in [
                502,  # Bad gateway
                503,  # Service unavailable
                504,
            ]:  # Gateway timeout
                raise RetryableJobError(
                    "A protocol error caused the failure of the job:\n"
                    f"URL: {err.url}\n"
                    f"HTTP/HTTPS headers: {err.headers}\n"
                    f"Error code: {err.errcode}\n"
                    f"Error message: {err.errmsg}\n"
                ) from err
            else:
                raise


class WooCRUDAdapter(AbstractComponent):
    """External Records Adapter for WooCommerce.

    The CRUD interface (``search``, ``read``, ``search_read``, ``create``,
    ``write`` and ``delete``) is provided by the connector base component
    ``base.backend.adapter.crud``. This component only implements the
    transport layer used to reach the WooCommerce REST API.
    """

    _name = "woocommerce.crud.adapter"
    _inherit = ["base.backend.adapter.crud", "base.woocommerce.connector"]
    _usage = "backend.adapter"

    def _call(self, method, arguments):
        try:
            wc_api = self.work.wc_api
        except AttributeError as err:
            raise AttributeError(
                "You must provide a wc_api attribute with a "
                "WooAPI instance to be able to use the "
                "Backend Adapter."
            ) from err
        return wc_api.call(method, arguments)


class GenericAdapter(AbstractComponent):
    _name = "woocommerce.adapter"
    _inherit = "woocommerce.crud.adapter"

    _woo_model = None

    def search(self, filters=None):
        """Search records according to some criterias
        and returns a list of ids

        :rtype: list
        """
        return self._call(f"{self._woo_model}.search", [filters] if filters else [{}])

    def read_record(self, external_id, attributes=None):
        """Returns the information of a record

        :rtype: dict
        """
        arguments = []
        if attributes:
            # Avoid to pass Null values in attributes. Workaround for
            # is not installed, calling info() with None in attributes
            # would return a wrong result (almost empty list of
            # attributes). The right correction is to install the
            # compatibility patch on WooCommerce.
            arguments.append(attributes)
        return self._call(f"{self._woo_model}/{external_id}", [])

    def search_read(self, filters=None):
        """Search records according to some criterias
        and returns their information"""
        return self._call(f"{self._woo_model}.list", [filters])
