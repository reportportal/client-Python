"""
Copyright (c) 2021 http://reportportal.io .

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""
import logging

from attrdict import AttrDict
from tenacity import retry, stop_after_attempt, wait_fixed

from .service import ReportPortalService

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


class ReportPortalReadService(ReportPortalService):
    """Service class with methods to read the data from Report Portal."""

    def __init__(self, endpoint, project, token, verify_ssl=True, **kwargs):
        """Init the service class.

        Args:
            endpoint: endpoint of report portal service.
            project: project name to use for launch names.
            token: authorization token.
            verify_ssl: option to not verify ssl certificates
        """
        super(ReportPortalReadService, self).__init__(
            endpoint=endpoint, project=project, token=token,
            verify_ssl=verify_ssl, **kwargs)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_fixed(5),
    )
    def get_launches(
            self, page=1, page_size=50, page_sort='startTime,desc', **filters):
        """Return all the launches in Report Portal filtered by filters.

        Usage Example:
            service = ReportPortalReadService(
                endpoint='rp.example.com', project='project')
            service.get_launches(
                filter_eq_status='failed', filter_eq_user='jyejare')
            service.get_launches(filter_eq_statistics__defects__automation_bug__ab001=1)
        Alternatively,
            service = ReportPortalReadService(
                endpoint='rp.example.com', project='project')
            params = {'filter.eq.status':'failed', 'filter.eq.user':'jyejare'}
            service.get_launches(**params)
            params = {'filter.eq.statistics$defects$automation_bug$ab001': 1}
            service.get_launches(**params)

        :param int page: The page number from where to start reading the data
        :param str page_size: Number of entries per page while reading the data
        :param str page_sort: Sort the data on the page,
            by default sorting with startTime in descending order

        :returns list: The list of AttrDict launches of Report portal.
        """
        params = {
            'page.page': page, 'page.size': page_size, 'page.sort': page_sort}
        params.update(filters)
        launches = []
        total_pages = page
        while page <= total_pages:
            params['page.page'] = page
            resp = self.read(component="launch", **params)
            attr_launches = [launch for launch in resp.json()['content']]
            launches.extend([AttrDict(lnch) for lnch in attr_launches])
            total_pages = resp.json()['page']['totalPages']
            page += 1
        return launches

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_fixed(5),
    )
    def get_tests(
            self, launch_id, isLatest=False, page=1, page_size=100,
            page_sort='desc', **filters):
        """Return all tests from the given launch ID, filtered by filters.

        Usage Example:
            service = ReportPortalReadService(
                endpoint='rp.example.com', project='project')
            service.get_tests(
                launch_id=315, filter_eq_status='failed',
                filter_eq_issueType='pb001')
            service.get_tests(
                launch_id=315,
                filter_eq_statistics__defects__automation_bug__ab001=1)
        Alternatively,
            service = ReportPortalReadService(
                endpoint='rp.example.com', project='project')
            params = {
                'filter.eq.status':'failed', 'filter.eq.issueType':'pb001'}
            service.get_tests(launch_id=315, **params)
            params = {'filter.eq.statistics$defects$automation_bug$ab001': 1}
            service.get_launches(launch_id=315, , **params)

        :param int launch_id: Launch ID of a launch to fetch the tests from
        :param bool isLatest: Sort by latest tests
        :param int page: The page number from where to start reading the data
        :param str page_size: Number of entries per page
        :param str page_sort: Sort the data on the page,
            by default sorting with descending order

        :returns list: The list of AttrDict tests from Report portal launch.
        """
        params = {
            'filter.eq.launchId': launch_id, 'isLatest': isLatest,
            'page.page': page, 'page.size': page_size, 'page.sort': page_sort}
        params.update(filters)
        tests = []
        total_pages = page
        while page <= total_pages:
            params['page.page'] = page
            resp = self.read(component='item', **params)
            tests.extend([AttrDict(tst) for tst in resp.json()['content']])
            total_pages = resp.json()['page']['totalPages']
            page += 1
        return tests
