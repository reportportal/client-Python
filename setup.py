from setuptools import setup, find_packages

setup(
    name='reportportal-client',
    packages=find_packages(),
    version='0.1.2',
    description='Python client for ReportPortal',
    author='Artsiom Tkachou',
    author_email='artsiom_tkachou@epam.com',
    url='https://github.com/epam/ReportPortal-Python-Client',
    download_url='https://github.com/epam/ReportPortal-Python-Client/tarball/0.1.2',
    keywords=['testing', 'reporting', 'reportportal'],
    classifiers=[],
    install_requires=[i.strip() for i in open("requirements.txt").readlines()],
)
