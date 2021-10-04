"""Config for setup package client Python."""

from setuptools import setup, find_packages

__version__ = '5.0.13'

with open('requirements.txt') as f:
    requirements = f.read().splitlines()

setup(
    name='reportportal-client',
    packages=find_packages(exclude=('tests', 'tests.*')),
    version=__version__,
    description='Python client for Report Portal v5.',
    author_email='SupportEPMC-TSTReportPortal@epam.com',
    url='https://github.com/reportportal/client-Python',
    download_url=('https://github.com/reportportal/client-Python/'
                  'tarball/%s' % __version__),
    license='Apache 2.0.',
    keywords=['testing', 'reporting', 'reportportal'],
    classifiers=[
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8'
    ],
    install_requires=requirements
)
