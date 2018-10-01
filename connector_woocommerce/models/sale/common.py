# © 2009 Tech-Receptives Solutions Pvt. Ltd.
# © 2018 Serpent Consulting Services Pvt. Ltd.
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
# See LICENSE file for full copyright and licensing details.

import logging

import xmlrpc.client
from odoo import models, fields, api
from odoo.addons.component.core import Component
from odoo.addons.connector.exception import IDMissingInBackend
from odoo.addons.queue_job.job import job, related_action

_logger = logging.getLogger(__name__)


class WooSaleOrderStatus(models.Model):
    _name = 'woo.sale.order.status'
    _description = 'WooCommerce Sale Order Status'

    name = fields.Char('Name')
    desc = fields.Text('Description')


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    status_id = fields.Many2one('woo.sale.order.status',
                                'WooCommerce Order Status')
    woo_bind_ids = fields.One2many(
        comodel_name='woo.sale.order',
        inverse_name='odoo_id',
        string="Woo Bindings",
    )
    # These fields are required for export
    sync_data = fields.Boolean("Synch with Woo?")
    woo_backend_id = fields.Many2one(
        'woo.backend',
        string="WooCommerce Store"
    )


class WooSaleOrder(models.Model):
    _name = 'woo.sale.order'
    _inherit = 'woo.binding'
    _inherits = {'sale.order': 'odoo_id'}
    _description = 'Woo Sale Order'

    _rec_name = 'name'

    status_id = fields.Many2one('woo.sale.order.status',
                                'WooCommerce Order Status')

    odoo_id = fields.Many2one(comodel_name='sale.order',
                              string='Sale Order',
                              required=True,
                              ondelete='cascade')
    woo_order_line_ids = fields.One2many(
        comodel_name='woo.sale.order.line',
        inverse_name='woo_order_id',
        string='Woo Order Lines'
    )
    backend_id = fields.Many2one(
        comodel_name='woo.backend',
        string='Woo Backend',
        store=True,
        readonly=False,
        required=True,
    )

    @job(default_channel='root.woo')
    @related_action(action='related_action_unwrap_binding')
    @api.multi
    def export_record(self):
        """ Export Sale orders. """
        for rec in self:
            rec.ensure_one()
            with rec.backend_id.work_on(rec._name) as work:
                exporter = work.component(usage='sale.order.exporter')
                return exporter.run(self)


class WooSaleOrderLine(models.Model):
    _name = 'woo.sale.order.line'
    _inherits = {'sale.order.line': 'odoo_id'}

    woo_order_id = fields.Many2one(
        comodel_name='woo.sale.order',
        string='Woo Sale Order',
        required=True,
        ondelete='cascade',
        index=True
    )
    odoo_id = fields.Many2one(
        comodel_name='sale.order.line',
        string='Sale Order Line',
        required=True,
        ondelete='cascade'
    )
    backend_id = fields.Many2one(
        related='woo_order_id.backend_id',
        string='Woo Backend',
        readonly=True,
        store=True,
        required=False,
    )

    @api.model
    def create(self, vals):
        woo_order_id = vals['woo_order_id']
        binding = self.env['woo.sale.order'].browse(woo_order_id)
        vals['order_id'] = binding.odoo_id.id
        binding = super(WooSaleOrderLine, self).create(vals)
        return binding


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    woo_bind_ids = fields.One2many(
        comodel_name='woo.sale.order.line',
        inverse_name='odoo_id',
        string="WooCommerce Bindings",
    )


class SaleOrderAdapter(Component):
    _name = 'woo.sale.order.adapter'
    _inherit = 'woo.adapter'
    _apply_on = 'woo.sale.order'

    _woo_model = 'orders'

    def _call(self, method, resource, arguments):
        try:
            return super(SaleOrderAdapter, self)._call(
                method,
                resource,
                arguments
            )
        except xmlrpc.client.Fault as err:
            # this is the error in the Woo API
            # when the customer does not exist
            if err.faultCode == 102:
                raise IDMissingInBackend
            else:
                raise

    def search(self, method=None, filters=None,
               from_date=None, to_date=None):
        """ Search records according to some criteria and return a
        list of ids

        :rtype: list
        """
        WOO_DATETIME_FORMAT = '%Y/%m/%d %H:%M:%S'
        dt_fmt = WOO_DATETIME_FORMAT
        if from_date is not None:
            # updated_at include the created records
            filters.setdefault('updated_at', {})
            filters['updated_at']['from'] = from_date.strftime(dt_fmt)
        if to_date is not None:
            filters.setdefault('updated_at', {})
            filters['updated_at']['to'] = to_date.strftime(dt_fmt)

        res = self._call(method, 'orders/', [filters] if filters else [{}])
        # Set sale order ids and return it(Due to new Wordpress version)
        order_ids = list()
        for order in res.get('orders'):
            order_ids.append(order.get('id'))
        return order_ids

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
        return self._call('get', '%s/' % self._woo_model + str(id), [])

    def create(self, data):
        """ Create a record on the external system """
        data = {
            "order": data
        }
        return self._call('post', self._woo_model, data)

    def write(self, id, data):
        """ Update records on the external system """
        data = {
            "order": data
        }
        return self._call('put', self._woo_model + "/" + str(id), data)

    def is_woo_record(self, woo_id, filters=None):
        """
        This method is to verify the existing record on WooCommerce.
        @param: woo_id : External id (int)
        @param: filters : Filters to check (json)
        @return: result : Response of Woocom (Boolean)
        """
        self._call(
            'get',
            self._woo_model + '/' + str(woo_id),
            filters
        )
        return True
