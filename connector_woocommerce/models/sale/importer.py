# © 2009 Tech-Receptives Solutions Pvt. Ltd.
# © 2018 Serpent Consulting Services Pvt. Ltd.
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
# See LICENSE file for full copyright and licensing details.

import logging

from odoo.addons.component.core import Component
from odoo.addons.connector.components.mapper import mapping

_logger = logging.getLogger(__name__)


class SaleOrderLineImportMapper(Component):
    _name = 'woo.sale.order.line.mapper'
    _inherit = 'woo.import.mapper'
    _apply_on = 'woo.sale.order.line'

    direct = [('quantity', 'product_uom_qty'),
              ('name', 'name'),
              ('price', 'price_unit')
              ]

    @mapping
    def product_id(self, record):
        binder = self.binder_for('woo.product.product')
        product_id = binder.to_internal(record['product_id'], unwrap=True)
        assert product_id is not None,\
            ("product_id %s should have been imported in "
             "SaleOrderImporter._import_dependencies" % record['product_id'])
        return {'product_id': product_id.id}


class SaleOrderBatchImporter(Component):
    """ Import the WooCommerce Partners.

    For every partner in the list, a delayed job is created.
    """
    _name = 'woo.sale.order.batch.importer'
    _inherit = 'woo.delayed.batch.importer'
    _apply_on = 'woo.sale.order'

    def _import_record(self, woo_id):
        """ Delay a job for the import """
        super(SaleOrderBatchImporter, self)._import_record(
            woo_id)

    def update_existing_order(self, woo_sale_order, record_id):
        """ Enter Your logic for Existing Sale Order """
        return True

    def run(self, filters=None):
        """ Run the synchronization """
        from_date = filters.pop('from_date', None)
        to_date = filters.pop('to_date', None)
        record_ids = self.backend_adapter.search(
            method='get',
            filters=filters,
            from_date=from_date,
            to_date=to_date,
        )
        saleOrder_ref = self.env['woo.sale.order']
        order_ids = []
        record = []
        # Get external ids from odoo for comparison
        saleOrder_rec = saleOrder_ref.search([('external_id', '!=', '')])
        for ext_id in saleOrder_rec:
            record.append(int(ext_id.external_id))
        # Get difference ids
        diff = list(set(record) - set(record_ids))
        for del_woo_rec in diff:
            woo_saleOrder_id = saleOrder_ref.search(
                [('external_id', '=', del_woo_rec)])
            saleOrder_id = woo_saleOrder_id.odoo_id
            odoo_saleOrder_id = self.env['sale.order'].search(
                [('id', '=', saleOrder_id.id)])
            # Delete reference from odoo
            odoo_saleOrder_id.write({
                'woo_bind_ids': [(3, odoo_saleOrder_id.woo_bind_ids[0].id)],
                'sync_data': False,
                'woo_backend_id': None
            })

        for record_id in record_ids:
            woo_sale_order = saleOrder_ref.search(
                [('external_id', '=', record_id)])
            if woo_sale_order:
                self.update_existing_order(woo_sale_order[0], record_id)
            else:
                order_ids.append(record_id)
        _logger.info('search for woo partners %s returned %s',
                     filters, record_ids)
        for record_id in order_ids:
            self._import_record(record_id)


class SaleOrderImporter(Component):
    _name = 'woo.sale.order.importer'
    _inherit = 'woo.importer'
    _apply_on = 'woo.sale.order'

    def _import_customer(self):
        record = self.woo_record
        record = record['order']
        self._import_dependency(record['customer_id'],
                                'woo.res.partner')

    def _import_dependencies(self):
        """ Import the dependencies for the record"""
        record = self.woo_record

        self._import_customer()
        record = record['items']
        for line in record:
            _logger.debug('line: %s', line)
            if 'product_id' in line:
                self._import_dependency(line['product_id'],
                                        'woo.product.product')

    def _clean_woo_items(self, resource):
        """
        Method that clean the sale order line given by WooCommerce before
        importing it

        This method has to stay here because it allow to customize the
        behavior of the sale order.

        """
        child_items = {}  # key is the parent item id
        top_items = []

        # Group the childs with their parent
        for item in resource['order']['line_items']:
            if item.get('parent_item_id'):
                child_items.setdefault(item['parent_item_id'], []).append(item)
            else:
                top_items.append(item)

        all_items = []
        for top_item in top_items:
            all_items.append(top_item)
        resource['items'] = all_items
        return resource

    def _create(self, data):
        odoo_binding = super(SaleOrderImporter, self)._create(data)
        # Adding Creation Checkpoint
        self.backend_record.add_checkpoint(odoo_binding)
        return odoo_binding

    def _update(self, binding, data):
        """ Update an Odoo record """
        super(SaleOrderImporter, self)._update(binding, data)
        return

    def _before_import(self):
        """ Hook called before the import"""
        return

    def _after_import(self, binding):
        """ Hook called at the end of the import """
        # Calling partner onchange of SO.
        binding.odoo_id.onchange_partner_id()
        return

    def _get_woo_data(self):
        """ Return the raw WooCommerce data for ``self.woo_id`` """
        record = super(SaleOrderImporter, self)._get_woo_data()
        # sometimes we need to clean woo items (ex : configurable
        # product in a sale)
        record = self._clean_woo_items(record)
        return record


class SaleOrderImportMapper(Component):
    _name = 'woo.sale.order.mapper'
    _inherit = 'woo.import.mapper'
    _apply_on = 'woo.sale.order'

    children = [('items', 'woo_order_line_ids', 'woo.sale.order.line'), ]

    @mapping
    def status(self, record):
        if record['order']:
            rec = record['order']
            if rec['status'] == 'pending':
                rec['status'] = 'draft'
            elif rec['status'] in ['processing', 'refunded', 'on-hold']:
                rec['status'] = 'sale'
            elif rec['status'] == 'completed':
                rec['status'] = 'done'
            elif rec['status'] in ['cancelled', 'failed']:
                rec['status'] = 'cancel'
            if rec['status']:
                status_id = self.env['woo.sale.order.status'].sudo().search(
                    [('name', '=', rec['status'])])
                if status_id:
                    return {'status_id': status_id[0].id,
                            'state': rec['status'],
                            }
                else:
                    status_id = self.env['woo.sale.order.status'].sudo(). \
                        create({'name': rec['status']})
                    return {'status_id': status_id.id,
                            'state': rec['status'],
                            }
            else:
                return {'status_id': False,
                        'state': rec['status'],
                        }

    @mapping
    def customer_id(self, record):
        if record['order']:
            rec = record['order']
            binder = self.binder_for('woo.res.partner')
            if rec['customer_id']:
                partner_id = binder.to_internal(rec['customer_id'],
                                                unwrap=True) or False
                assert partner_id, ("Please Check Customer Role \
                                    in WooCommerce")
                result = {'partner_id': partner_id.id}
            else:
                customer = rec['customer']['billing_address']
                country_id = False
                state_id = False
                if customer['country']:
                    country_id = self.env['res.country'].search(
                        [('code', '=', customer['country'])], limit=1)
                    if country_id:
                        country_id = country_id.id
                if customer['state']:
                    state_id = self.env['res.country.state'].search(
                        [('code', '=', customer['state'])], limit=1)
                    if state_id:
                        state_id = state_id.id
                name = customer['first_name'] + ' ' + customer['last_name']
                partner_dict = {
                    'name': name,
                    'city': customer['city'],
                    'phone': customer['phone'],
                    'zip': customer['postcode'],
                    'state_id': state_id,
                    'country_id': country_id
                }
                partner_id = self.env['res.partner'].create(partner_dict)
                result = {'partner_id': partner_id.id}
            return result

    @mapping
    def backend_id(self, record):
        return {'backend_id': self.backend_record.id}

    # Required for export
    @mapping
    def sync_data(self, record):
        if record.get('order'):
            return {'sync_data': True}

    @mapping
    def woo_backend_id(self, record):
        return {'woo_backend_id': self.backend_record.id}
