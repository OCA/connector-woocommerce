# Copyright 2009 Tech-Receptives Solutions Pvt. Ltd.
# Copyright 2018 FactorLibre
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, models, fields
from odoo.addons.connector.exception import RetryableJobError


class WooBinding(models.AbstractModel):
    _name = "woo.binding"
    _inherit = "external.binding"
    _description = "Woo Binding (abstract)"

    # openerp_id = openerp-side id must be declared in concrete model
    backend_id = fields.Many2one(
        comodel_name="wc.backend",
        string="Woo Backend",
        required=True,
        ondelete="restrict",
    )
    # fields.Char because 0 is a valid WooCommerce ID
    external_id = fields.Char(string="ID on Woo")

    _sql_constraints = [
        ("woo_uniq", "unique(backend_id, external_id)",
         "A binding already exists with the same Woo ID."),
    ]

    def check_active(self, backend):
        if not backend.active:
            raise RetryableJobError(
                "Backend %s is inactive please consider changing this"
                "The job will be retried later." % (backend.name,)
            )

    @api.model
    def import_batch(self, backend, filters=None):
        """ Prepare the import of records modified on  Woocommerce"""
        if not filters:
            filters = {}
        self.check_active(backend)
        with backend.work_on(self._name) as work:
            importer = work.component(usage="batch.importer")
            return importer.run(filters=filters)

    @api.model
    def import_record(self, backend, external_id, force=False):
        """ Import a Woocommerce record """
        self.check_active(backend)
        with backend.work_on(self._name) as work:
            importer = work.component(usage="record.importer")
            return importer.run(external_id, force=force)

    def export_record(self, fields=None):
        """ Export a record on Woocommerce """
        self.ensure_one()
        self.check_active(self.backend_id)
        with self.backend_id.work_on(self._name) as work:
            exporter = work.component(usage="record.exporter")
            return exporter.run(self, fields)

    def export_delete_record(self, backend, external_id):
        """ Delete a record on Woocommerce """
        self.check_active(backend)
        with backend.work_on(self._name) as work:
            deleter = work.component(usage="record.exporter.deleter")
            return deleter.run(external_id)
