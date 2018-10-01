# Copyright 2013-2017 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo.addons.component.core import Component
from odoo.addons.connector.components.mapper import changed_by, mapping, \
    only_create


class SaleOrderExporter(Component):
    _name = 'woo.sale.order.exporter'
    _inherit = ['woo.exporter', 'woo.base.exporter']
    _apply_on = ['woo.sale.order']
    _usage = 'sale.order.exporter'

    def _after_export(self):
        """ After Export"""
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
        # Export Customer
        if record.partner_id:
            self._export_dependency(
                record.partner_id,
                'woo.res.partner',
                component_usage='res.partner.exporter'
            )
        # Export Products
        if record.order_line:
            for line in record.order_line:
                self._export_dependency(
                    line.product_id,
                    'woo.product.product',
                    component_usage='product.product.exporter'
                )
        return


class SaleOrderExportMapper(Component):
    _name = 'woo.sale.order.export.mapper'
    _inherit = 'woo.export.mapper'
    _apply_on = ['woo.sale.order']

    @changed_by('partner_id')
    @mapping
    def customer(self, record):
        if record.partner_id:
            binder = self.binder_for("woo.res.partner")
            customer_id = binder.to_external(record.partner_id, wrap=True)
            return {"customer_id": customer_id}

    @mapping
    def billing(self, record):
        ivoice = record.partner_invoice_id
        data = {}
        name = ivoice.name.split(" ")
        data.update({
            "first_name": name[0],
            "last_name": " ".join(name[1:]),
            "company": ivoice.company_name,
            "address_1": ivoice.street,
            "address_2": ivoice.street2,
            "city": ivoice.city,
            "postcode": ivoice.zip,
            "email": ivoice.email,
            "phone": ivoice.phone,
            "state": ivoice.state_id and ivoice.state_id.code or False,
            "country": ivoice.country_id and ivoice.country_id.code or False
        })
        return {'billing_address': data}

    @mapping
    def shipping(self, record):
        shipping = record.partner_shipping_id
        data = {}
        name = shipping.name.split(" ")
        data.update({
            "first_name": name[0],
            "last_name": " ".join(name[1:]),
            "company": shipping.company_name,
            "address_1": shipping.street,
            "address_2": shipping.street2,
            "city": shipping.city,
            "postcode": shipping.zip,
            "state": shipping.state_id and shipping.state_id.code or False,
            "country": shipping.country_id and shipping.country_id.code or
            False
        })
        return {'shipping_address': data}

    @changed_by('state')
    @mapping
    def status(self, record):
        if record.state == 'draft':
            return {'status': 'pending'}
        elif record.state == 'done':
            return {'status': 'completed'}
        elif record.state == 'sale':
            return {'status': 'processing'}
        elif record.state == 'cancel':
            return {'status': 'cancelled'}

    @only_create
    @mapping
    def orderline_create(self, record):
        items = []
        if record.order_line:
            for line in record.order_line:
                binder = self.binder_for("woo.product.product")
                product_id = binder.to_external(
                    line.product_id,
                    wrap=True
                )
                items.append({
                    "product_id": product_id,
                    # SKU can be used instead of product_id, while mapping.
                    "quantity": line.product_uom_qty,
                    "total": line.price_unit
                })
            return {"line_items": items}

    @mapping
    def orderline_update(self, record):
        """ Eneter your Logic here to Update order lines """
        return
