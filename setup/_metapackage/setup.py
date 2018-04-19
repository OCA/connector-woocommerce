import setuptools

with open('VERSION.txt', 'r') as f:
    version = f.read().strip()

setuptools.setup(
    name="odoo8-addons-oca-connector-woocommerce",
    description="Meta package for oca-connector-woocommerce Odoo addons",
    version=version,
    install_requires=[
        'odoo8-addon-connector_woocommerce',
    ],
    classifiers=[
        'Programming Language :: Python',
        'Framework :: Odoo',
    ]
)
