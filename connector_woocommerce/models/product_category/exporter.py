# Copyright 2013-2017 Camptocamp SA
# © 2018 Serpent Consulting Services Pvt. Ltd.
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo.addons.component.core import Component
from odoo.addons.connector.components.mapper import mapping, changed_by


class ProductCategoryExporter(Component):
    _name = 'woo.product.category.exporter'
    _inherit = ['woo.exporter', 'woo.base.exporter']
    _apply_on = ['woo.product.category']
    _usage = 'product.category.exporter'

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

    def _export_dependencies(self):
        """ Export the dependencies for the record"""
        record = self.binding.odoo_id
        if record.parent_id:
            self._export_dependency(
                self.binding.odoo_id.parent_id,
                'woo.product.category',
                component_usage='product.category.exporter'
            )
        return


class ProductCategoryExportMapper(Component):
    _name = 'woo.product.category.export.mapper'
    _inherit = 'woo.export.mapper'
    _apply_on = ['woo.product.category']

    @changed_by('name')
    @mapping
    def name(self, record):
        return {"name": record.name}

    @changed_by('parent_id')
    @mapping
    def parent(self, record):
        binder = self.binder_for("woo.product.category")
        category_id = False
        if record.parent_id:
            # Get id of product.category model
            category_id = binder.to_external(record.parent_id, wrap=True)
        return {'parent': category_id}
