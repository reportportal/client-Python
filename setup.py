from setuptools import setup, find_packages

__version__ = '5.0.0'

setup(
    name='reportportal-client',
    packages=find_packages(),
    version=__version__,
    description='Python client for Report Portal v5.',
    author_email='SupportEPMC-TSTReportPortal@epam.com',
    url='https://github.com/reportportal/client-Python',
    download_url=('https://github.com/reportportal/client-Python/'
                  'tarball/%s' % __version__),
    license='Apache 2.0.',
    keywords=['testing', 'reporting', 'reportportal'],
    classifiers=[],
    install_requires=['requests>=2.4.2', 'six'],
)
