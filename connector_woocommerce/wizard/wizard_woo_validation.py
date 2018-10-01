# © 2009 Tech-Receptives Solutions Pvt. Ltd.
# © 2018 Serpent Consulting Services Pvt. Ltd.
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
# See LICENSE file for full copyright and licensing details.

'''Wizard to check for deleted record from WooCommerce in
reference is still in Odoo the delete that reference and create new one
record in WooCommerce'''
from odoo import api, models


class WooValidation(models.TransientModel):
    _name = 'wizard.woo.validation'

    @api.multi
    def woo_validate(self):
        context = self.env.context
        # Get odoo id
        odoo_id = context.get('odoo_id')
        # Get Backend id
        backend_id = context.get("backend_id")
        record = None
        import_obj = None

        # Set record for specific model
        if context.get("active_model") == 'res.partner':
            import_obj = self.env['woo.res.partner']
            record = self.env['res.partner'].search([('id', '=', odoo_id)])

        if context.get("active_model") == 'product.category':
            import_obj = self.env['woo.product.category']
            record = self.env['product.category'].search(
                [('id', '=', odoo_id)])

        if context.get("active_model") == 'product.product':
            import_obj = self.env['woo.product.product']
            record = self.env['product.product'].search([('id', '=', odoo_id)])

        # Delete record from odoo
        record.write({
            'woo_bind_ids': [(3, record.woo_bind_ids[0].id)],
            'sync_data': False,
            'woo_backend_id': None
        })
        # Build environment to export
        import_id = import_obj.create({
            'backend_id': backend_id,
            'odoo_id': odoo_id,
        })
        # Do export
        import_id.with_delay().export_record()
