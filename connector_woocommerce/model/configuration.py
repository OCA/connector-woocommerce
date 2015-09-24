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
import logging
import xmlrpclib
from openerp import models, fields
from openerp.addons.connector.unit.mapper import (mapping,
                                                  ImportMapper
                                                  )
from openerp.addons.connector.exception import IDMissingInBackend
from ..unit.backend_adapter import (GenericAdapter)
from ..unit.import_synchronizer import (DelayedBatchImporter, WooImporter)
from ..backend import woo
_logger = logging.getLogger(__name__)


class Configuration(models.Model):
    _name = 'configuration'
    _rec_name = 'currency'
    currency = fields.Many2one('res.currency',
                               string="WooCommerce Currency",
                               readonly=True)
    currency_position = fields.Char(string="Currency Position", readonly=True)
    decimal_seperator = fields.Char(string="Decimal Seperator", readonly=True)
    decimals = fields.Integer(string="Decimals", readonly=True)
    thousand_seperator = fields.Char(
        string="Thousand Seperator", readonly=True)
    country = fields.Many2many('res.country', string="Countries")


class WooConfiguration(models.Model):
    _name = 'woo.configuration'
    _inherit = 'woo.binding'
    _inherits = {'configuration': 'openerp_id'}

    openerp_id = fields.Many2one(
        'configuration',
        string='Configuration',
        required=True,
        ondelete='cascade'
    )


@woo
class ConfigurationAdapter(GenericAdapter):
    _model_name = 'woo.configuration'
    _woo_model = 'settings/general'

    def _call(self, method, arguments):
        try:
            return super(ConfigurationAdapter, self)._call(method, arguments)
        except xmlrpclib.Fault as err:
            # this is the error in the WooCommerce API
            # when the customer does not exist
            if err.faultCode == 102:
                raise IDMissingInBackend
            else:
                raise
#

    def search(self, filters=None, from_date=None, to_date=None):
        """ Search records according to some criteria and return a
        list of ids

        :rtype: list
        """
        if filters is None:
            filters = {}
        WOO_DATETIME_FORMAT = '%Y/%m/%d %H:%M:%S'
        dt_fmt = WOO_DATETIME_FORMAT
        if from_date is not None:
            filters.setdefault('updated_at', {})
            filters['updated_at']['from'] = from_date.strftime(dt_fmt)
        if to_date is not None:
            filters.setdefault('updated_at', {})
            filters['updated_at']['to'] = to_date.strftime(dt_fmt)
        return self._call('settings/general',
                          [filters] if filters else [{}])


@woo
class ConfigurationBatchImporter(DelayedBatchImporter):

    """ Import the WooCommerce Partners.

    For every partner in the list, a delayed job is created.
    """
    _model_name = ['woo.configuration']

    def _import_record(self, woo_id, priority=None):
        """ Delay a job for the import """
        super(ConfigurationBatchImporter, self)._import_record(
            woo_id, priority=priority)
#

    def run(self, filters=None):
        """ Run the synchronization """
        record_ids = self.backend_adapter.search(
            filters)
        _logger.info('search for woo Cuurency Method %s returned %s',
                     filters, record_ids)
#         for record_id in record_ids:
        self._import_record(1)

ConfigurationBatchImporter = ConfigurationBatchImporter


@woo
class ConfigurationImporter(WooImporter):
    _model_name = ['woo.configuration']

    def _import_dependencies(self):
        """ Import the dependencies for the record"""
        # import parent category
        # the root category has a 0 parent_id
        return

    def _create(self, data):
            openerp_binding = super(ConfigurationImporter, self)._create(data)
            return openerp_binding

    def _after_import(self, binding):
        """ Hook called at the end of the import """
        return

ConfigurationImporter = ConfigurationImporter


@woo
class ConfigurationImportMapper(ImportMapper):
    _model_name = 'woo.configuration'

    @mapping
    def name(self, record):
        return {'currency_position': record['Currency Position'] or False,
                'decimal_seperator': record['Decimal Seperator']or False,
                'thousand_seperator': record['Thousand Seperator']or False,
                'decimals': record['Decimals']or False}

    @mapping
    def currency(self, record):
        currency = self.env['res.currency'].search(
            [('name', '=', record['Currency'])])
        return {'currency': currency.id}

    @mapping
    def country(self, record):
        country_ids = []
        specific_countries = record['Specific_Countries']
        for specific_country in specific_countries:
            country = self.env['res.country'].search(
                [('code', '=', specific_country)])
            if country:
                country_ids.append(country.id)
        return {'country': [(6, 0, country_ids)]}

    @mapping
    def backend_id(self, record):
        return {'backend_id': self.backend_record.id}
