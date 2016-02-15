# -*- coding: utf-8 -*-
#
#
#    Tech-Receptives Solutions Pvt. Ltd.
#    Copyright (C) 2009-TODAY Tech-Receptives(<http://www.techreceptives.com>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
#

import socket
import logging
import xmlrpclib
from woocommerce import API

from openerp.addons.connector.unit.backend_adapter import CRUDAdapter
from openerp.addons.connector.exception import (NetworkRetryableError,
                                                RetryableJobError)
from openerp.tools.safe_eval import safe_eval

from datetime import datetime
_logger = logging.getLogger(__name__)

recorder = {}


def call_to_key(method, arguments):
    """ Used to 'freeze' the method and arguments of a call to WooCommerce
    so they can be hashable; they will be stored in a dict.

    Used in both the recorder and the tests.
    """
    def freeze(arg):
        if isinstance(arg, dict):
            items = dict((key, freeze(value)) for key, value
                         in arg.iteritems())
            return frozenset(items.iteritems())
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
    with open(filename, 'w') as f:
        pprint.pprint(recorder, f)
    _logger.debug('recorder written to file %s', filename)


class WooLocation(object):

    def __init__(self, location, consumer_key, consumre_secret):
        self._location = location
        self.consumer_key = consumer_key
        self.consumer_secret = consumre_secret

    @property
    def location(self):
        location = self._location
        return location


class WooCRUDAdapter(CRUDAdapter):

    """ External Records Adapter for woo """

    def __init__(self, connector_env):
        """

        :param connector_env: current environment (backend, session, ...)
        :type connector_env: :class:`connector.connector.ConnectorEnvironment`
        """
        super(WooCRUDAdapter, self).__init__(connector_env)
        backend = self.backend_record
        woo = WooLocation(
            backend.location,
            backend.consumer_key,
            backend.consumer_secret)
        self.woo = woo

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
            _logger.debug("Start calling Woocommerce api %s", method)
            api = API(url=self.woo.location,
                      consumer_key=self.woo.consumer_key,
                      consumer_secret=self.woo.consumer_secret,
                      version='v2')
            if api:
                if isinstance(arguments, list):
                    while arguments and arguments[-1] is None:
                        arguments.pop()
                start = datetime.now()
                try:
                    if 'false' or 'true' or 'null'in api.get(method).content:
                        result = api.get(method).content.replace(
                            'false', 'False')
                        result = result.replace('true', 'True')
                        result = result.replace('null', 'False')
                        result = safe_eval(result)
                    else:
                        result = safe_eval(api.get(method).content)
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
                'A network error caused the failure of the job: '
                '%s' % err)
        except xmlrpclib.ProtocolError as err:
            if err.errcode in [502,   # Bad gateway
                               503,   # Service unavailable
                               504]:  # Gateway timeout
                raise RetryableJobError(
                    'A protocol error caused the failure of the job:\n'
                    'URL: %s\n'
                    'HTTP/HTTPS headers: %s\n'
                    'Error code: %d\n'
                    'Error message: %s\n' %
                    (err.url, err.headers, err.errcode, err.errmsg))
            else:
                raise


class GenericAdapter(WooCRUDAdapter):

    _model_name = None
    _woo_model = None

    def search(self, filters=None):
        """ Search records according to some criterias
        and returns a list of ids

        :rtype: list
        """
        return self._call('%s.search' % self._woo_model,
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
        return self._call('%s/' % self._woo_model + str(id), [])

    def search_read(self, filters=None):
        """ Search records according to some criterias
        and returns their information"""
        return self._call('%s.list' % self._woo_model, [filters])

    def create(self, data):
        """ Create a record on the external system """
        return self._call('%s.create' % self._woo_model, [data])

    def write(self, id, data):
        """ Update records on the external system """
        return self._call('%s.update' % self._woo_model,
                          [int(id), data])

    def delete(self, id):
        """ Delete a record on the external system """
        return self._call('%s.delete' % self._woo_model, [int(id)])
