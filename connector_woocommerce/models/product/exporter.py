# Copyright 2013-2017 Camptocamp SA
# © 2018 Serpent Consulting Services Pvt. Ltd.
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo.addons.component.core import Component
from odoo.addons.connector.components.mapper import mapping, changed_by
from odoo.addons.connector.exception import InvalidDataError


class ProductProductExporter(Component):
    _name = 'woo.product.product.exporter'
    _inherit = ['woo.exporter', 'woo.base.exporter']
    _apply_on = ['woo.product.product']
    _usage = 'product.product.exporter'

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

        if not data.get('email'):
            raise InvalidDataError("The partner does not have an email "
                                   "but it is mandatory for Woo")
        return

    def _get_data(self, binding, fields):
        result = {}
        return result

    def _export_dependencies(self):
        """ Export the dependencies for the record"""
        record = self.binding.odoo_id
        if record.categ_id:
            self._export_dependency(
                record.categ_id,
                'woo.product.category',
                component_usage='product.category.exporter'
            )
        return


class ProductProductExportMapper(Component):
    _name = 'woo.product.product.export.mapper'
    _inherit = 'woo.export.mapper'
    _apply_on = ['woo.product.product']

    @changed_by('name')
    @mapping
    def name(self, record):
        data = {
            "name": record.name,
            "title": record.name
        }
        return data

    @changed_by('category_id')
    @mapping
    def sku(self, record):
        if record.default_code:
            return {'sku': record.default_code}

    @changed_by('default_code')
    @mapping
    def categories(self, record):
        if record.categ_id:
            binder = self.binder_for("woo.product.category")
            category_id = binder.to_external(record.categ_id, wrap=True)
            return {"categories": [category_id]}

    @changed_by('list_price')
    @mapping
    def sale_price(self, record):
        return {'regular_price': record.list_price}
