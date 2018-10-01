# Copyright 2013-2017 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo.addons.component.core import Component
from odoo.addons.connector.components.mapper import mapping, changed_by


class ShippingZoneExporter(Component):
    _name = 'woo.shipping.zone.exporter'
    _inherit = ['woo.exporter', 'woo.base.exporter']
    _apply_on = ['woo.shipping.zone']
    _usage = 'shipping.zone.exporter'

    def _after_export(self):
        """After Export"""
        self.binding.odoo_id.sudo().write({
            'sync_data': True,
            'woo_backend_id': self.backend_record.id
        })
        return

    def _validate_create_data(self, data):
        """ Check if the values to import are correct

        Pro-actively check before the ``Model.create`` or
        ``Model.update`` if some fields are missing

        Raise `InvalidDataError`
        """
        return

    def _get_data(self, binding, fields):
        result = {}
        return result


class ShippingZoneExportMapper(Component):
    _name = 'woo.shipping.zone.export.mapper'
    _inherit = 'woo.export.mapper'
    _apply_on = ['woo.shipping.zone']

    @changed_by('name')
    @mapping
    def name(self, record):
        return {"name": record.name}
