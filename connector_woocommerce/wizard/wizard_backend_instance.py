# © 2009 Tech-Receptives Solutions Pvt. Ltd.
# © 2018 Serpent Consulting Services Pvt. Ltd.
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
# See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class WooBackendInstance(models.TransientModel):
    _name = 'wizard.backend.instance'

    instance = fields.Many2many('woo.backend', 'woo_backend_instance_rel',
                                'name', required=True, string="Shops")

    # Import Product operations fields
    import_product = fields.Boolean()

    # Import Product Category Operations fields
    import_product_category = fields.Boolean()

    # Import Customer operations fields
    import_customer = fields.Boolean()

    # Import Sale Order operations fields
    import_sale_order = fields.Boolean()

    import_shippingzone = fields.Boolean()

    # Export Product operations fields
    export_product = fields.Boolean()
    update_product = fields.Boolean()

    # Export Product Category Operations fields
    export_product_category = fields.Boolean()
    update_product_category = fields.Boolean()

    # Export Customer operations fields
    export_customer = fields.Boolean()
    update_customer = fields.Boolean()

    # Export Sale Order operations fields
    export_sale_order = fields.Boolean()
    update_sale_order = fields.Boolean()

    # Export Delivery Carrier operations fields
    export_shippingzone = fields.Boolean()
    update_shippingzone = fields.Boolean()

    @api.multi
    def woo_backend_instance(self):
        # Check that user has selected Shops or not
        if self.instance:
            instances = self.instance
            # Checks that user has selected any
            #  import/export operations or not
            if not any(
                    self.export_shippingzone, self.update_shippingzone,
                    self.import_shippingzone, self.import_product,
                    self.import_product_category, self.import_customer,
                    self.import_sale_order, self.export_product,
                    self.update_product, self.export_product_category,
                    self.update_product_category, self.export_customer,
                    self.update_customer, self.export_sale_order,
                    self.update_sale_order):
                raise ValidationError(_("Please Select Any Operation..."))

            # Check and call import operations from WooCommerce to Odoo
            if self.import_shippingzone:
                instances.import_shippingzone()
            if self.import_product:
                instances.import_products()
            if self.import_product_category:
                instances.import_categories()
            if self.import_customer:
                instances.import_customers()
            if self.import_sale_order:
                instances.import_orders()

            # Check and call export/update operations from Odoo to WooCommerce
            if self.export_product or self.update_product:
                if self.export_product and self.update_product:
                    context = {'export_product': True, 'update_product': True}
                elif self.export_product and self.update_product:
                    context = {
                        'export_product': True,
                        'update_product': False
                    }
                elif self.update_product and \
                        self.export_product:
                    context = {
                        'export_product': False,
                        'update_product': True
                    }
                instances.with_context(context).export_product()

            if self.export_product_category or \
                    self.update_product_category:
                if self.export_product_category and \
                        self.update_product_category:
                    context = {'export_product_category': True,
                               'update_product_category': True}
                elif self.export_product_category and \
                        self.update_product_category:
                    context = {'export_product_category': True,
                               'update_product_category': False}
                elif self.update_product_category and \
                        self.export_product_category:
                    context = {'export_product_category': False,
                               'update_product_category': True}
                instances.with_context(context).export_category()

            if self.export_customer or self.update_customer:
                if self.export_customer and \
                        self.update_customer:
                    context = {'export_customer': True,
                               'update_customer': True}
                elif self.export_customer and \
                        self.update_customer:
                    context = {'export_customer': True,
                               'update_customer': False}
                elif self.update_customer and \
                        self.export_customer:
                    context = {'export_customer': False,
                               'update_customer': True}
                instances.with_context(context).export_customer()

            if self.export_sale_order or \
                    self.update_sale_order:
                if self.export_sale_order and \
                        self.update_sale_order:
                    context = {'export_sale_order': True,
                               'update_sale_order': True}
                elif self.export_sale_order and \
                        self.update_sale_order:
                    context = {'export_sale_order': True,
                               'update_sale_order': False}
                elif self.update_sale_order and \
                        self.export_sale_order:
                    context = {'export_sale_order': False,
                               'update_sale_order': True}
                instances.with_context(context).export_saleorder()

            if self.export_shippingzone or \
                    self.update_shippingzone:
                if self.export_shippingzone and \
                        self.update_shippingzone:
                    context = {'export_shippingzone': True,
                               'update_shippingzone': True}
                elif self.export_shippingzone and \
                        self.update_shippingzone:
                    context = {'export_shippingzone': True,
                               'update_shippingzone': False}
                elif self.update_shippingzone and \
                        self.export_shippingzone:
                    context = {'export_shippingzone': False,
                               'update_shippingzone': True}
                instances.with_context(context).export_shippingzone()
