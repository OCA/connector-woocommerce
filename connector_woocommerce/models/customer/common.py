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


class WooResPartner(models.Model):
    _name = 'woo.res.partner'
    _inherit = 'woo.binding'
    _inherits = {'res.partner': 'odoo_id'}
    _description = 'woo res partner'

    _rec_name = 'name'

    odoo_id = fields.Many2one(comodel_name='res.partner',
                              string='Partner',
                              required=True,
                              ondelete='cascade')
    backend_id = fields.Many2one(
        comodel_name='woo.backend',
        string='Woo Backend',
        store=True,
        readonly=False,
    )

    @job(default_channel='root.woo')
    @related_action(action='related_action_unwrap_binding')
    @api.multi
    def export_record(self):
        """ Export a Customer. """
        for rec in self:
            rec.ensure_one()
            with rec.backend_id.work_on(rec._name) as work:
                exporter = work.component(usage='res.partner.exporter')
                return exporter.run(self)


class ResPartner(models.Model):
    _inherit = 'res.partner'

    woo_bind_ids = fields.One2many(
        comodel_name='woo.res.partner',
        inverse_name='odoo_id',
        string="Woo Bindings",
    )
    # These fields are required for export
    sync_data = fields.Boolean("Synch with Woo?")
    woo_backend_id = fields.Many2one(
        'woo.backend',
        string="WooCommerce Store"
    )


class CustomerAdapter(Component):
    _name = 'woo.partner.adapter'
    _inherit = 'woo.adapter'
    _apply_on = 'woo.res.partner'

    _woo_model = 'customers'

    def _call(self, method, resource, arguments):
        try:
            return super(CustomerAdapter, self)._call(
                method,
                resource,
                arguments
            )
        except xmlrpc.client.Fault as err:
            # this is the error in the WooCommerce API
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
        # the search method is on ol_customer instead of customer
        res = self._call(method, 'customers', [filters] if filters else [{}])

        # Set customer ids and return it(Due to new WooCommerce REST API)
        customer_ids = list()
        for customer in res.get('customers'):
            customer_ids.append(customer.get('id'))
        return customer_ids

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
            "customer": data
        }
        return self._call('post', self._woo_model, data)

    def write(self, id, data):
        """ Update records on the external system """
        data = {
            "customer": data
        }
        return self._call('put', self._woo_model + "/" + str(id), data)

    def is_woo_record(self, woo_id, filters=None):
        """
        This method is to verify the existing record on WooCommerce.
        @param: woo_id : External id (int)
        @param: filters : Filters to check (json)
        @return: result : Response of Woocom (Boolean)
        """
        return self._call('get', self._woo_model + '/' + str(woo_id), filters)
