# -*- coding: utf-8 -*-
#
#
#    TechSpawn Solutions Pvt. Ltd.
#    Copyright (C) 2016-TODAY TechSpawn(<http://www.techspawn.com>).
#    authors : Vinay Bhawsar, Saumil Thaker, Samir Panda
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.


{
    'name': 'WooCommerce Connector',
    'version': '8.0.1.0.2',
    'category': 'customized',
    'description': """Techspawn WooCommerce Connector.""",
    'author': 'Techspawn',
    'maintainer': 'OpenERP SA',
    'website': 'http://www.openerp.com',
    'depends': ['base', 'connector', 'connector_ecommerce'],
    'installable': True,
    'auto_install': False,
    'data': [
        "security/ir.model.access.csv",
        "views/backend_view.xml",
    ],
    'external_dependencies': {
        'python': ['woocommerce'],
    },
    'js': [],
    'application': True,
    "sequence": 3,
}
