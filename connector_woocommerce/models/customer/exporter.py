# Copyright 2013-2017 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo.addons.component.core import Component
from odoo.addons.connector.components.mapper import changed_by, mapping, \
    only_create
from odoo.addons.connector.exception import InvalidDataError


class CustomerExporter(Component):
    _name = 'woo.res.partner.exporter'
    _inherit = ['woo.exporter', 'woo.base.exporter']
    _apply_on = ['woo.res.partner']
    _usage = 'res.partner.exporter'

    def _after_export(self):
        "After Import"
        self.binding.odoo_id.sudo().write({
            'sync_data': True,
            'woo_backend_id': self.backend_record.id
        })

    def _validate_create_data(self, data):
        """ Check if the values to import are correct

        Pro-actively check before the ``Model.create`` or
        ``Model.update`` if some fields are missing

        Raise `InvalidDataError`
        """
        if not data.get('email'):
            raise InvalidDataError(
                "The partner does not have an email "
                "but it is mandatory for Woo"
            )
        if not data.get("shipping_address"):
            address = data.get("billing_address")
            address.pop('email')
            address.pop('phone')
            data.update(shipping_address=address)
        return

    def _get_data(self, binding, fields):
        result = {}
        return result


class CustomerExportMapper(Component):
    _name = 'woo.res.partner.export.mapper'
    _inherit = 'woo.export.mapper'
    _apply_on = ['woo.res.partner']

    @changed_by('name')
    @mapping
    def name(self, record):
        name = record.name.split(" ")
        data = {
            "first_name": name[0],
            "last_name": " ".join(name[1:])
        }
        return data

    @changed_by('email')
    @mapping
    def email(self, record):
        data = {
            "email": record.email,
        }
        return data

    @only_create
    @changed_by('email')
    @mapping
    def username(self, record):
        data = dict()
        if not record.external_id:
            data.update(username=record.email, password=record.email)
        return data

    @mapping
    def billing(self, record):
        data = {}
        name = record.name.split(" ")
        data.update({
            "first_name": name[0],
            "last_name": " ".join(name[1:]),
            "company": record.company_name,
            "address_1": record.street,
            "address_2": record.street2,
            "city": record.city,
            "postcode": record.zip,
            "email": record.email,
            "phone": record.phone,
            "state": record.state_id and record.state_id.code or False,
            "country": record.country_id and record.country_id.code or False
        })
        return {'billing_address': data}

    @mapping
    def shipping(self, record):
        data = {}
        partner_obj = self.env["res.partner"]
        ship_id = partner_obj.search([
            ('parent_id', '=', record.odoo_id.id),
            ('type', '=', 'delivery')],
            limit=1,
            order='write_date desc')
        if ship_id:
            name = ship_id.name.split(" ")
            data.update({
                "first_name": name[0],
                "last_name": " ".join(name[1:]),
                "company": ship_id.company_name,
                "address_1": ship_id.street,
                "address_2": ship_id.street2,
                "city": ship_id.city,
                "postcode": ship_id.zip,
                "state": ship_id.state_id and ship_id.state_id.code or False,
                "country": ship_id.country_id and ship_id.country_id.code or
                False
            })
            return {'shipping_address': data}
