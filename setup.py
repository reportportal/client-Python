from setuptools import setup, find_packages

setup(
    name='reportportal-client',
    packages=find_packages(),
    version='3.0.0',
    description='Python client for Report Portal',
    author='Artsiom Tkachou',
    author_email='SupportEPMC-TSTReportPortal@epam.com',
    url='https://github.com/reportportal/client-Python',
    download_url='https://github.com/reportportal/client-Python/tarball/3.0.0',
    license='GNU General Public License v3',
    keywords=['testing', 'reporting', 'reportportal'],
    classifiers=[],
    install_requires=['requests>=2.4.2'],
)
