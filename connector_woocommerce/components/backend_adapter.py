# Copyright 2009 Tech-Receptives Solutions Pvt. Ltd.
# Copyright 2018 FactorLibre
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
import socket
import logging
import xmlrpc.client
from odoo.addons.component.core import AbstractComponent
from odoo.addons.queue_job.exception import FailedJobError
from odoo.addons.connector.exception import (NetworkRetryableError,
                                             RetryableJobError)
from datetime import datetime
_logger = logging.getLogger(__name__)

try:
    from woocommerce import API
except ImportError:
    _logger.debug("cannot import 'woocommerce'")

recorder = {}

WOO_DATETIME_FORMAT = "%Y/%m/%d %H:%M:%S"


def call_to_key(method, arguments):
    """ Used to "freeze" the method and arguments of a call to WooCommerce
    so they can be hashable; they will be stored in a dict.

    Used in both the recorder and the tests.
    """
    def freeze(arg):
        if isinstance(arg, dict):
            items = dict((key, freeze(value)) for key, value
                         in arg.items())
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
    """ Utility function which can be used to record test data
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


class WooLocation(object):

    def __init__(self, location, consumer_key, consumer_secret):
        self._location = location
        self.consumer_key = consumer_key
        self.consumer_secret = consumer_secret

    @property
    def location(self):
        location = self._location
        return location


class WooAPI(object):

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
                version="wc/v2"
            )
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
                    if response_json.get("code") and \
                            response_json.get("message"):
                        raise FailedJobError(
                            "%s error: %s - %s" % (response.status_code,
                                                   response_json["code"],
                                                   response_json["message"]))
                    else:
                        return response.raise_for_status()
                result = response_json
            except:
                _logger.error("api.call(%s, %s) failed", method, arguments)
                raise
            else:
                _logger.debug("api.call(%s, %s) returned %s in %s seconds",
                              method, arguments, result,
                              (datetime.now() - start).seconds)
            return result
        except (socket.gaierror, socket.error, socket.timeout) as err:
            raise NetworkRetryableError(
                "A network error caused the failure of the job: "
                "%s" % err)
        except xmlrpc.client.ProtocolError as err:
            if err.errcode in [502,   # Bad gateway
                               503,   # Service unavailable
                               504]:  # Gateway timeout
                raise RetryableJobError(
                    "A protocol error caused the failure of the job:\n"
                    "URL: %s\n"
                    "HTTP/HTTPS headers: %s\n"
                    "Error code: %d\n"
                    "Error message: %s\n" %
                    (err.url, err.headers, err.errcode, err.errmsg))
            else:
                raise


class WooCRUDAdapter(AbstractComponent):
    """ External Records Adapter for woo """

    _name = "woocommerce.crud.adapter"
    _inherit = ["base.backend.adapter", "base.woocommerce.connector"]
    _usage = "backend.adapter"

    def search(self, filters=None):
        """ Search records according to some criterias
        and returns a list of ids """
        raise NotImplementedError

    def read(self, id, attributes=None):
        """ Returns the information of a record """
        raise NotImplementedError

    def search_read(self, filters=None):
        """ Search records according to some criterias
        and returns their information"""
        raise NotImplementedError

    def create(self, data):
        """ Create a record on the external system """
        raise NotImplementedError

    def write(self, id, data):
        """ Update records on the external system """
        raise NotImplementedError

    def delete(self, id):
        """ Delete a record on the external system """
        raise NotImplementedError

    def _call(self, method, arguments):
        try:
            wc_api = getattr(self.work, "wc_api")
        except AttributeError:
            raise AttributeError(
                "You must provide a wc_api attribute with a "
                "WooAPI instance to be able to use the "
                "Backend Adapter."
            )
        return wc_api.call(method, arguments)


class GenericAdapter(AbstractComponent):

    _name = "woocommerce.adapter"
    _inherit = "woocommerce.crud.adapter"

    _woo_model = None

    def search(self, filters=None):
        """ Search records according to some criterias
        and returns a list of ids

        :rtype: list
        """
        return self._call("%s.search" % self._woo_model,
                          [filters] if filters else [{}])

    def read(self, id, attributes=None):
        """ Returns the information of a record

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
        return self._call("%s/" % self._woo_model + str(id), [])

    def search_read(self, filters=None):
        """ Search records according to some criterias
        and returns their information"""
        return self._call("%s.list" % self._woo_model, [filters])

    def create(self, data):
        """ Create a record on the external system """
        return self._call("%s.create" % self._woo_model, [data])

    def write(self, id, data):
        """ Update records on the external system """
        return self._call("%s.update" % self._woo_model,
                          [int(id), data])

    def delete(self, id):
        """ Delete a record on the external system """
        return self._call("%s.delete" % self._woo_model, [int(id)])
