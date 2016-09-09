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

import logging
from openerp import fields, _
from openerp.addons.connector.queue.job import job, related_action
from openerp.addons.connector.unit.synchronizer import Importer
from openerp.addons.connector.exception import IDMissingInBackend
from ..connector import get_environment
from ..related_action import link
from datetime import datetime
_logger = logging.getLogger(__name__)


class WooImporter(Importer):

    """ Base importer for WooCommerce """

    def __init__(self, connector_env):
        """
        :param connector_env: current environment (backend, session, ...)
        :type connector_env: :class:`connector.connector.ConnectorEnvironment`
        """
        super(WooImporter, self).__init__(connector_env)
        self.woo_id = None
        self.woo_record = None

    def _get_woo_data(self):
        """ Return the raw WooCommerce data for ``self.woo_id`` """
        return self.backend_adapter.read(self.woo_id)

    def _before_import(self):
        """ Hook called before the import, when we have the WooCommerce
        data"""

    def _is_uptodate(self, binding):
        """Return True if the import should be skipped because
        it is already up-to-date in OpenERP"""
        WOO_DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'
        dt_fmt = WOO_DATETIME_FORMAT
        assert self.woo_record
        if not self.woo_record:
            return  # no update date on WooCommerce, always import it.
        if not binding:
            return  # it does not exist so it should not be skipped
        sync = binding.sync_date
        if not sync:
            return
        from_string = fields.Datetime.from_string
        sync_date = from_string(sync)
        self.woo_record['updated_at'] = {}
        self.woo_record['updated_at'] = {'to': datetime.now().strftime(dt_fmt)}
        woo_date = from_string(self.woo_record['updated_at']['to'])
        # if the last synchronization date is greater than the last
        # update in woo, we skip the import.
        # Important: at the beginning of the exporters flows, we have to
        # check if the woo_date is more recent than the sync_date
        # and if so, schedule a new import. If we don't do that, we'll
        # miss changes done in WooCommerce
        return woo_date < sync_date

    def _import_dependency(self, woo_id, binding_model,
                           importer_class=None, always=False):
        """ Import a dependency.

        The importer class is a class or subclass of
        :class:`WooImporter`. A specific class can be defined.

        :param woo_id: id of the related binding to import
        :param binding_model: name of the binding model for the relation
        :type binding_model: str | unicode
        :param importer_cls: :class:`openerp.addons.connector.\
                                     connector.ConnectorUnit`
                             class or parent class to use for the export.
                             By default: WooImporter
        :type importer_cls: :class:`openerp.addons.connector.\
                                    connector.MetaConnectorUnit`
        :param always: if True, the record is updated even if it already
                       exists, note that it is still skipped if it has
                       not been modified on WooCommerce since the last
                       update. When False, it will import it only when
                       it does not yet exist.
        :type always: boolean
        """
        if not woo_id:
            return
        if importer_class is None:
            importer_class = WooImporter
        binder = self.binder_for(binding_model)
        if always or binder.to_openerp(woo_id) is None:
            importer = self.unit_for(importer_class, model=binding_model)
            importer.run(woo_id)

    def _import_dependencies(self):
        """ Import the dependencies for the record

        Import of dependencies can be done manually or by calling
        :meth:`_import_dependency` for each dependency.
        """
        return

    def _map_data(self):
        """ Returns an instance of
        :py:class:`~openerp.addons.connector.unit.mapper.MapRecord`

        """
        return self.mapper.map_record(self.woo_record)

    def _validate_data(self, data):
        """ Check if the values to import are correct

        Pro-actively check before the ``_create`` or
        ``_update`` if some fields are missing or invalid.

        Raise `InvalidDataError`
        """
        return

    def _must_skip(self):
        """ Hook called right after we read the data from the backend.

        If the method returns a message giving a reason for the
        skipping, the import will be interrupted and the message
        recorded in the job (if the import is called directly by the
        job, not by dependencies).

        If it returns None, the import will continue normally.

        :returns: None | str | unicode
        """
        return

    def _get_binding(self):
        return self.binder.to_openerp(self.woo_id, browse=True)

    def _create_data(self, map_record, **kwargs):
        return map_record.values(for_create=True, **kwargs)

    def _create(self, data):
        """ Create the OpenERP record """
        # special check on data before import
        self._validate_data(data)
        model = self.model.with_context(connector_no_export=True)
        model = str(model).split('()')[0]
        binding = self.env[model].create(data)
        _logger.debug('%d created from woo %s', binding, self.woo_id)
        return binding

    def _update_data(self, map_record, **kwargs):
        return map_record.values(**kwargs)

    def _update(self, binding, data):
        """ Update an OpenERP record """
        # special check on data before import
        self._validate_data(data)
        binding.with_context(connector_no_export=True).write(data)
        _logger.debug('%d updated from woo %s', binding, self.woo_id)
        return

    def _after_import(self, binding):
        """ Hook called at the end of the import """
        return

    def run(self, woo_id, force=False):
        """ Run the synchronization

        :param woo_id: identifier of the record on WooCommerce
        """
        self.woo_id = woo_id
        try:
            self.woo_record = self._get_woo_data()
        except IDMissingInBackend:
            return _('Record does no longer exist in WooCommerce')

        skip = self._must_skip()
        if skip:
            return skip

        binding = self._get_binding()
        if not force and self._is_uptodate(binding):
            return _('Already up-to-date.')
        self._before_import()

        # import the missing linked resources
        self._import_dependencies()

        map_record = self._map_data()

        if binding:
            record = self._update_data(map_record)
            self._update(binding, record)
        else:
            record = self._create_data(map_record)
            binding = self._create(record)
        self.binder.bind(self.woo_id, binding)

        self._after_import(binding)


WooImportSynchronizer = WooImporter


class BatchImporter(Importer):

    """ The role of a BatchImporter is to search for a list of
    items to import, then it can either import them directly or delay
    the import of each item separately.
    """

    def run(self, filters=None):
        """ Run the synchronization """
        record_ids = self.backend_adapter.search(filters)
        for record_id in record_ids:
            self._import_record(record_id)

    def _import_record(self, record_id):
        """ Import a record directly or delay the import of the record.

        Method to implement in sub-classes.
        """
        raise NotImplementedError


BatchImportSynchronizer = BatchImporter


class DirectBatchImporter(BatchImporter):

    """ Import the records directly, without delaying the jobs. """
    _model_name = None

    def _import_record(self, record_id):
        """ Import the record directly """
        import_record(self.session,
                      self.model._name,
                      self.backend_record.id,
                      record_id)


DirectBatchImport = DirectBatchImporter


class DelayedBatchImporter(BatchImporter):

    """ Delay import of the records """
    _model_name = None

    def _import_record(self, record_id, **kwargs):
        """ Delay the import of the records"""
        import_record.delay(self.session,
                            self.model._name,
                            self.backend_record.id,
                            record_id,
                            **kwargs)


DelayedBatchImport = DelayedBatchImporter


@job(default_channel='root.woo')
@related_action(action=link)
def import_record(session, model_name, backend_id, woo_id, force=False):
    """ Import a record from Woo """
    env = get_environment(session, model_name, backend_id)
    importer = env.get_connector_unit(WooImporter)
    importer.run(woo_id, force=force)
