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


class WooDeliveryCarrier(models.Model):
    _name = 'woo.delivery.carrier'
    _inherit = 'woo.binding'
    _inherits = {'delivery.carrier': 'odoo_id'}
    _description = 'woo delivery carrier'

    _rec_name = 'name'

    odoo_id = fields.Many2one(comodel_name='delivery.carrier',
                              string='Delivery',
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
        """ Export a DeliveryCarrier. """
        for rec in self:
            rec.ensure_one()
            with rec.backend_id.work_on(rec._name) as work:
                exporter = work.component(usage='delivery.carrier.exporter')
                return exporter.run(self)


class DeliveryCarrier(models.Model):
    _inherit = 'delivery.carrier'

    woo_bind_ids = fields.One2many(
        comodel_name='woo.delivery.carrier',
        inverse_name='odoo_id',
        string="Woo Bindings",
    )
    # These fields are required for export
    sync_data = fields.Boolean("Synch with Woo?")
    woo_backend_id = fields.Many2one(
        'woo.backend',
        string="WooCommerce Store"
    )


class DeliveryCarrierAdapter(Component):
    _name = 'woo.delivery.carier.adapter'
    _inherit = 'woo.adapter'
    _apply_on = 'woo.delivery.carrier'

    _woo_model = 'shipping/zones/'

    def _call(self, method, resource, arguments):
        try:
            return super(DeliveryCarrierAdapter, self)._call(
                method,
                resource,
                arguments
            )
        except xmlrpc.client.Fault as err:
            # this is the error in the WooCommerce API
            # when the Delivery Carrier does not exist
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
        res = self._call(method, 'shipping/zones/5/methods',
                         [filters] if filters else [{}])

        # Set delivery carrier ids and return
        # it(Due to new WooCommerce REST API)
        deliveryCarrier_ids = list()
        for delivery in res.get('shipping/zones/5/methods'):
            deliveryCarrier_ids.append(delivery.get('id'))
        return deliveryCarrier_ids

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
            "deliverycarier": data
        }
        return self._call('post', self._woo_model, data)

    def write(self, id, data):
        """ Update records on the external system """
        data = {
            "deliverycarier": data
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
