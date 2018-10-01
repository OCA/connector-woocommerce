# © 2009 Tech-Receptives Solutions Pvt. Ltd.
# © 2018 Serpent Consulting Services Pvt. Ltd.
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
# See LICENSE file for full copyright and licensing details.

import logging
from datetime import datetime
from odoo import _, api, fields, models
from odoo.exceptions import Warning

_logger = logging.getLogger(__name__)
try:
    from woocommerce import API
except ImportError:
    _logger.debug("Cannot import 'woocommerce'")


class WooExport(models.TransientModel):
    """
    Fields which are declared here must be passed also in
    "context" on woo export wizard action as woo_active_field.
    "context" values are case sensitive.
    <field name="context">{'woo_active_field': 'partner_ids'}</field>
    """
    _name = 'wizard.woo.export'
    _description = 'Wizard to export to WooCommerce.'

    @api.model
    def default_get(self, fields):
        res = super(WooExport, self).default_get(fields)
        context = self.env.context
        # target_field and active_ids are passed through context from action.
        active_field = context.get('woo_active_field')
        active_ids = context.get('active_ids')
        # Load the values
        res[active_field] = active_ids
        return res

    product_cate_ids = fields.Many2many(
        'product.category',
        string='Product Categories'
    )
    product_ids = fields.Many2many(
        'product.product',
        string='Products'
    )
    partner_ids = fields.Many2many(
        'res.partner',
        string='Partners'
    )
    order_ids = fields.Many2many(
        'sale.order',
        string='Sale Orders'
    )

    # Method to check that export record is exist in WooCommerce or not
    @api.multi
    def before_woo_validate(self, active_field, active_model, is_woo_data,
                            active_id):
        wac = self.env['woo.backend'].search([], limit=1)
        location = wac.location
        cons_key = wac.consumer_key
        sec_key = wac.consumer_secret
        version = wac.version or 'v3'

        # WooCommerce API Connection
        wcapi = API(
            url=location,  # Your store URL
            consumer_key=cons_key,  # Your consumer key
            consumer_secret=sec_key,  # Your consumer secret
            version=version,  # WooCommerce WP REST API version
            query_string_auth=True  # Force Basic Authentication as query
            # string true and using under HTTPS
        )
        method = "get"
        arguments = {}
        path = ''
        resource = ''
        # Set path based on active model
        if active_model == 'res.partner':
            path = "customers/"
        if active_model == 'product.category':
            path = "products/categories/"
        if active_model == 'product.product':
            path = "products/"
        # Set resource based on path
        if path != '':
            resource = path + str(is_woo_data.external_id)
        if wcapi:
            result = {}
            if isinstance(arguments, list):
                while arguments and arguments[-1] is None:
                    arguments.pop()
            start = datetime.now()
            try:
                wooapi = getattr(wcapi, method)
                res = wooapi(resource) if method not in ['put', 'post'] \
                    else wooapi(resource, arguments)
                vals = res.json()
                invalid_record_flag = 0
                # Check that if record is deleted from WooCommerce or not
                if 'errors' in vals and \
                        vals['errors'][0].get('code') == \
                        'woocommerce_api_invalid_product_category_id':
                    invalid_record_flag = 1
                if 'errors' in vals and vals['errors'][0].get(
                        'code') == 'woocommerce_api_invalid_product_id':
                    invalid_record_flag = 1
                if 'errors' in vals and vals['errors'][0].get(
                        'code') == 'woocommerce_api_invalid_customer':
                    invalid_record_flag = 1
                # If record is deleted from WooCommerce then return False
                if invalid_record_flag == 1:
                    invalid_record_flag = 0
                    return False
            except Exception as e:
                _logger.error("api.call(%s, %s, %s, %s) failed", method,
                              resource,
                              arguments, e)
                raise
            else:
                _logger.debug("api.call(%s, %s, %s) returned %s in %s\
                seconds", method, resource, arguments, result,
                              (datetime.now() - start).seconds)
            return True

    @api.multi
    def woo_export(self):
        """"
        This method exports the Odoo data to WooCommerce.
        Object and methods are managed dynamically based on context values.
        Woo Backend Id is mandatory for exporting.
        @param: self (Current Object)
        @return: True
        @type: Boolean
        """
        context = self.env.context
        active_field = context.get('woo_active_field')
        active_model = context.get('active_model')
        for rec in self:
            # browse data of active_model with active_ids
            active_field_ids = getattr(rec, str(active_field))
            import_obj = rec.env["woo.%s" % active_model]
            for active_id in active_field_ids:
                if not active_id.woo_backend_id:
                    raise Warning(_(
                        "WooCommerce Backend is missing! \n"
                        " Record : %s\n"
                        " ID : %s" %
                        (active_id.display_name, active_id.id)
                    ))
                is_woo_data = import_obj.search(
                    [('odoo_id', '=', active_id.id)], limit=1)
                if is_woo_data:
                    # Call method to check that export record
                    #  is exist in WooCommerce or not
                    result = self.before_woo_validate(active_field,
                                                      active_model,
                                                      is_woo_data, active_id)

                    if not result:
                        return {
                            'name': _('Invalid Record'),
                            'type': 'ir.actions.act_window',
                            'view_type': 'form',
                            'view_mode': 'form',
                            'view_id': self.env.ref(
                                'connector_woocommerce.'
                                'woo_validation_form_view').id,
                            'res_model': 'wizard.woo.validation',
                            'target': 'new',
                            'context': {
                                'is_woo_data': is_woo_data.id,
                                'active_field': active_field,
                                'active_model': active_model,
                                'odoo_id': is_woo_data.odoo_id.id,
                                'external_id': is_woo_data.external_id,
                                'backend_id': active_id.woo_backend_id.id, },
                        }
                    is_woo_data.with_delay().export_record()
                else:
                    # Build environment to export
                    import_id = import_obj.create({
                        'backend_id': active_id.woo_backend_id.id,
                        'odoo_id': active_id.id,
                    })
                    import_id.with_delay().export_record()
            return True
