# Copyright 2009 Tech-Receptives Solutions Pvt. Ltd.
# Copyright 2018 FactorLibre
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
{
    "name": "WooCommerce Connector",
    "version": "12.0.1.0.0",
    "category": "Connector",
    "author": "Tech Receptives,"
              "FactorLibre,"
              "Odoo Community Association (OCA)",
    "license": "AGPL-3",
    "website": "https://github.com/OCA/connector-woocommerce/",
    "maintainers": ["cubells"],
    "depends": [
        "connector",
        "product_multi_category",
        "sale_stock",
    ],
    "installable": True,
    "data": [
        "security/ir.model.access.csv",
        "views/backend_views.xml",
    ],
    "external_dependencies": {
        "python": ["woocommerce"],
    },
    "application": True,
}
