# Copyright 2009 Tech-Receptives Solutions Pvt. Ltd.
# Copyright 2018 FactorLibre
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo.addons.component.core import AbstractComponent


class WooImportMapper(AbstractComponent):
    _name = "woocommerce.import.mapper"
    _inherit = ["base.import.mapper", "base.woocommerce.connector"]
    _usage = "import.mapper"


class WooExportMapper(AbstractComponent):
    _name = "woocommerce.export.mapper"
    _inherit = ["base.export.mapper", "base.woocommerce.connector"]
    _usage = "export.mapper"


def normalize_datetime(field):
    """Change a invalid date which comes from Woo, if
    no real date is set to null for correct import to
    OpenERP"""

    def modifier(self, record, to_attr):
        if record[field] == "0000-00-00 00:00:00":
            return None
        return record[field]
    return modifier
