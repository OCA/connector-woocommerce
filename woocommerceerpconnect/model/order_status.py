import logging
import xmlrpclib

from openerp import models, fields
from openerp.addons.connector.exception import IDMissingInBackend
from openerp.addons.connector.queue.job import job
from openerp.addons.connector.unit.mapper import (mapping,
                                                  ImportMapper
                                                  )
from ..backend import woo
from ..connector import get_environment
from ..unit.backend_adapter import (GenericAdapter)
from ..unit.import_synchronizer import (DelayedBatchImporter, WooImporter)
_logger = logging.getLogger(__name__)


class sale_order_state(models.Model):
    _name = 'sale.order.state'

    name = fields.Char('Name', size=128, translate=True)
#     company_id= fields.Many2one('res.company', 'Company', required=True)
    woo_bind_ids = fields.One2many(
        'woo.sale.order.state',
        'openerp_id',
        string="Woo Bindings"
    )


class woo_sale_order_state(models.Model):
    _name = 'woo.sale.order.state'
    _inherit = 'woo.binding'
    _inherits = {'sale.order.state': 'openerp_id'}

    openerp_state_ids = fields.One2many(
        'sale.order.state.list',
        'woo_state_id',
        'OpenERP States'
    )
    openerp_id = fields.Many2one(
        'sale.order.state',
        string='Sale Order State',
        required=True,
        ondelete='cascade'
    )


@woo
class SaleOrderStateAdapter(GenericAdapter):
    _model_name = 'woo.sale.order.state'
    _woo_model = 'orders/details/status'

    def _call(self, method, arguments):
        try:
            return super(SaleOrderStateAdapter, self)._call(method, arguments)
        except xmlrpclib.Fault as err:
            # this is the error in the Woo API
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
            # updated_at include the created records
            filters.setdefault('updated_at', {})
            filters['updated_at']['from'] = from_date.strftime(dt_fmt)
        if to_date is not None:
            filters.setdefault('updated_at', {})
            filters['updated_at']['to'] = to_date.strftime(dt_fmt)

        return self._call('orders/details/status/list',
                          [filters] if filters else [{}])


@woo
class SaleOrderStateBatchImporter(DelayedBatchImporter):

    """ Import the WooCommerce Partners.

    For every partner in the list, a delayed job is created.
    """
    _model_name = ['woo.sale.order.state']

    def _import_record(self, woo_id, priority=None):
        """ Delay a job for the import """
        super(SaleOrderStateBatchImporter, self)._import_record(
            woo_id, priority=priority)

    def run(self, filters=None):
        """ Run the synchronization """
        from_date = filters.pop('from_date', None)
        to_date = filters.pop('to_date', None)
        record_ids = self.backend_adapter.search(
            filters,
            from_date=from_date,
            to_date=to_date,
        )
        _logger.info('search for woo order status %s returned %s',
                     filters, record_ids)
        for record_id in record_ids:
            self._import_record(record_id, 30)


SaleOrderStateBatchImporter = SaleOrderStateBatchImporter


@woo
class SaleOrderStatedImporter(WooImporter):
    _model_name = ['woo.sale.order.state']

    def _import_dependencies(self):
        """ Import the dependencies for the record"""
        # import parent category
        # the root category has a 0 parent_id
        return

    def _create(self, data):
        openerp_binding = super(SaleOrderStatedImporter, self)._create(data)
        return openerp_binding

    def _after_import(self, binding):
        """ Hook called at the end of the import """
        return

SaleOrderStatedImporter = SaleOrderStatedImporter


@woo
class SaleOrderStateMapper(ImportMapper):
    _model_name = 'woo.sale.order.state'

    direct = [
        ('name', 'name'),
    ]

    @mapping
    def name(self, record):
        return {'name': record['name']}

    @mapping
    def backend_id(self, record):
        return {'backend_id': self.backend_record.id}

#     @mapping
#     def company_id(self, record):
#         return {'company_id': self.backend_record.company_id.id}


@job(default_channel='root.woo')
def order_state_import_batch(session, model_name, backend_id, filters=None):
    """ Prepare the import of product modified on Woo """
    if filters is None:
        filters = {}
    env = get_environment(session, model_name, backend_id)
    importer = env.get_connector_unit(SaleOrderStateBatchImporter)
    importer.run(filters=filters)


class sale_order_state_list(models.Model):
    _name = 'sale.order.state.list'

    name = fields.Selection(
        [
            ('draft', 'Draft Quotation'),
            ('sent', 'Quotation Sent'),
            ('cancel', 'Cancelled'),
            ('waiting_date', 'Waiting Schedule'),
            ('progress', 'Sales Order'),
            ('manual', 'Sale to Invoice'),
            ('invoice_except', 'Invoice Exception'),
            ('done', 'Done'),
        ],
        'OpenERP State',
        required=True
    )
    woo_state_id = fields.Many2one(
        'woo.sale.order.state',
        'Woo State'
    )
    woo_id = fields.Char(
        related='woo_state_id.woo_id',
        string='Woo ID',
        readonly=True,
        store=True
    )
