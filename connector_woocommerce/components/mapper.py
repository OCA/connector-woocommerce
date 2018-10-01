# © 2009 Tech-Receptives Solutions Pvt. Ltd.
# © 2018 Serpent Consulting Services Pvt. Ltd.
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
# See LICENSE file for full copyright and licensing details.

from odoo.addons.component.core import AbstractComponent


class WooImportMapper(AbstractComponent):
    _name = 'woo.import.mapper'
    _inherit = ['base.woo.connector', 'base.import.mapper']
    _usage = 'import.mapper'


class WooExportMapper(AbstractComponent):
    _name = 'woo.export.mapper'
    _inherit = ['base.woo.connector', 'base.export.mapper']
    _usage = 'export.mapper'


def normalize_datetime(field):
    """Change a invalid date which comes from Woo, if
    no real date is set to null for correct import to
    Odoo"""

    def modifier(self, record, to_attr):
        if record[field] == '0000-00-00 00:00:00':
            return None
        return record[field]
    return modifier
