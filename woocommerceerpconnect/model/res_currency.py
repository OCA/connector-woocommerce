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


class woo_res_currency(models.Model):
    _name = 'woo.res.currency'
    _inherit = 'woo.binding'
    _inherits = {'res.currency': 'openerp_id'}

    openerp_id = fields.Many2one(
        'res.currency',
        string='Currency',
        required=True,
        ondelete='cascade'
    )

    _sql_constraints = [
        ('woo_uniq', 'unique(backend_id, woo_id)',
         'A Currency with the same ID on wooID already exists.'),
    ]


@woo
class ResCurrencyAdapter(GenericAdapter):
    _model_name = 'woo.res.currency'
    _woo_model = 'currencies'

    def _call(self, method, arguments):
        try:
            return super(ResCurrencyAdapter, self)._call(method, arguments)
        except xmlrpclib.Fault as err:
            # this is the error in the WooCommerce API
            # when the customer does not exist
            if err.faultCode == 102:
                raise IDMissingInBackend
            else:
                raise

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
        return self._call('currencies/list',
                          [filters] if filters else [{}])


@woo
class CurrencyBatchImporter(DelayedBatchImporter):

    """ Import the WooCommerce Partners.

    For every partner in the list, a delayed job is created.
    """
    _model_name = ['woo.res.currency']

    def _import_record(self, woo_id, priority=None):
        """ Delay a job for the import """
        super(CurrencyBatchImporter, self)._import_record(
            woo_id, priority=priority)

    def run(self, filters=None):
        """ Run the synchronization """
        record_ids = self.backend_adapter.search(
            filters)
        _logger.info('search for woo Cuurency Method %s returned %s',
                     filters, record_ids)
        for record_id in record_ids:
            self._import_record(record_id)

CurrencyBatchImporter = CurrencyBatchImporter


@woo
class CurrencyImporter(WooImporter):
    _model_name = ['woo.res.currency']

    def _import_dependencies(self):
        """ Import the dependencies for the record"""
        # import parent category
        # the root category has a 0 parent_id
        return

    def _create(self, data):
        currency = self.env['res.currency'].search(
            [('name', '=', data['name'])])
        if not currency:
            openerp_binding = super(CurrencyImporter, self)._create(data)
            return openerp_binding

    def _after_import(self, binding):
        """ Hook called at the end of the import """
        return

CurrencyImporter = CurrencyImporter


@woo
class CurrencyImportMapper(ImportMapper):
    _model_name = 'woo.res.currency'

    @mapping
    def name(self, record):
        if record['code']:
            return {'name': record['code']}

    @mapping
    def backend_id(self, record):
        return {'backend_id': self.backend_record.id}
