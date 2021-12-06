"""This module contains Report Portal Client class.

Copyright (c) 2018 http://reportportal.io .

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
import requests
from requests.adapters import HTTPAdapter

from reportportal_client.core.log_manager import LogManager
from reportportal_client.core.rp_requests import (
    HttpRequest,
    ItemStartRequest,
    ItemFinishRequest,
    LaunchStartRequest,
    LaunchFinishRequest
)
from reportportal_client.helpers import uri_join, verify_value_length

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


class RPClient(object):
    """Report portal client."""

    def __init__(self,
                 endpoint,
                 project,
                 token,
                 log_batch_size=20,
                 is_skipped_an_issue=True,
                 verify_ssl=True,
                 retries=None,
                 max_pool_size=50,
                 launch_id=None,
                 **_):
        """Initialize required attributes.

        :param endpoint:             Endpoint of the report portal service
        :param project:              Project name to report to
        :param token:                Authorization token
        :param log_batch_size:       Option to set the maximum number of
                                     logs that can be processed in one batch
        :param is_skipped_an_issue:  Option to mark skipped tests as not
                                     'To Investigate' items on the server side
        :param verify_ssl:           Option to skip ssl verification
        :param max_pool_size:        Option to set the maximum number of
                                     connections to save the pool.
        """
        self._batch_logs = []
        self.api_v1, self.api_v2 = 'v1', 'v2'
        self.endpoint = endpoint
        self.project = project
        self.base_url_v1 = uri_join(
            self.endpoint, 'api/{}'.format(self.api_v1), self.project)
        self.base_url_v2 = uri_join(
            self.endpoint, 'api/{}'.format(self.api_v2), self.project)
        self.is_skipped_an_issue = is_skipped_an_issue
        self.launch_id = launch_id
        self.log_batch_size = log_batch_size
        self.token = token
        self.verify_ssl = verify_ssl
        self.session = requests.Session()
        if retries:
            self.session.mount('https://', HTTPAdapter(
                max_retries=retries, pool_maxsize=max_pool_size))
            self.session.mount('http://', HTTPAdapter(
                max_retries=retries, pool_maxsize=max_pool_size))
        self.session.headers['Authorization'] = 'bearer {0}'.format(self.token)

        self._log_manager = LogManager(
            self.endpoint, self.session, self.api_v2, self.launch_id,
            self.project, log_batch_size=log_batch_size)

    def finish_launch(self,
                      end_time,
                      status=None,
                      attributes=None,
                      **kwargs):
        """Finish launch.

        :param end_time:    Launch end time
        :param status:      Launch status. Can be one of the followings:
                            PASSED, FAILED, STOPPED, SKIPPED, RESETED,
                            CANCELLED
        :param attributes:  Launch attributes
        """
        url = uri_join(self.base_url_v2, 'launch', self.launch_id, 'finish')
        request_payload = LaunchFinishRequest(
            end_time,
            status=status,
            attributes=attributes,
            description=kwargs.get('description')
        ).payload
        response = HttpRequest(self.session.put, url=url, json=request_payload,
                               verify_ssl=self.verify_ssl).make()
        logger.debug('finish_launch - ID: %s', self.launch_id)
        logger.debug('response message: %s', response.message)
        return response.message

    def finish_test_item(self,
                         item_id,
                         end_time,
                         status,
                         issue=None,
                         attributes=None,
                         description=None,
                         retry=False,
                         **kwargs):
        """Finish suite/case/step/nested step item.

        :param item_id:     ID of the test item
        :param end_time:    Test item end time
        :param status:      Test status. Allowable values: "passed",
                            "failed", "stopped", "skipped", "interrupted",
                            "cancelled"
        :param attributes:  Test item attributes(tags). Pairs of key and value.
                            Overrides attributes on start
        :param description: Test item description. Overrides description
                            from start request.
        :param issue:       Issue of the current test item
        :param retry:       Used to report retry of the test. Allowable values:
                           "True" or "False"
        """
        url = uri_join(self.base_url_v2, 'item', item_id)
        request_payload = ItemFinishRequest(
            end_time,
            self.launch_id,
            status,
            attributes=attributes,
            description=description,
            is_skipped_an_issue=self.is_skipped_an_issue,
            issue=issue,
            retry=retry
        ).payload
        response = HttpRequest(self.session.put, url=url, json=request_payload,
                               verify_ssl=self.verify_ssl).make()
        logger.debug('finish_test_item - ID: %s', item_id)
        logger.debug('response message: %s', response.message)
        return response.message

    def get_item_id_by_uuid(self, uuid):
        """Get test item ID by the given UUID.

        :param uuid: UUID returned on the item start
        :return:     Test item ID
        """
        url = uri_join(self.base_url_v1, 'item', 'uuid', uuid)
        response = HttpRequest(self.session.get, url=url,
                               verify_ssl=self.verify_ssl).make()
        return response.id

    def get_launch_info(self):
        """Get the current launch information.

        :return dict: Launch information in dictionary
        """
        if self.launch_id is None:
            return {}
        url = uri_join(self.base_url_v1, 'launch', 'uuid', self.launch_id)
        logger.debug('get_launch_info - ID: %s', self.launch_id)
        response = HttpRequest(self.session.get, url=url,
                               verify_ssl=self.verify_ssl).make()
        if response.is_success:
            launch_info = response.json
            logger.debug(
                'get_launch_info - Launch info: %s', response.json)
        else:
            logger.warning('get_launch_info - Launch info: '
                           'Failed to fetch launch ID from the API.')
            launch_info = {}
        return launch_info

    def get_launch_ui_id(self):
        """Get UI ID of the current launch.

        :return: UI ID of the given launch. None if UI ID has not been found.
        """
        return self.get_launch_info().get('id')

    def get_launch_ui_url(self):
        """Get UI URL of the current launch.

        :return: launch URL or all launches URL.
        """
        ui_id = self.get_launch_ui_id() or ''
        path = 'ui/#{0}/launches/all/{1}'.format(self.project, ui_id)
        url = uri_join(self.endpoint, path)
        logger.debug('get_launch_ui_url - ID: %s', self.launch_id)
        return url

    def get_project_settings(self):
        """Get project settings.

        :return: HTTP response in dictionary
        """
        url = uri_join(self.base_url_v1, 'settings')
        response = HttpRequest(self.session.get, url=url, json={},
                               verify_ssl=self.verify_ssl).make()
        return response.json

    def log(self, time, message, level=None, attachment=None, item_id=None):
        """Send log message to the Report Portal.

        :param time:       Time in UTC
        :param message:    Log message
        :param level:      Message's log level
        :param attachment: Message attachments
        :param item_id:    ID of the RP item the message belongs to
        """
        self._log_manager.log(time, message, level, attachment, item_id)

    def start(self):
        """Start the client."""
        self._log_manager.start()

    def start_launch(self,
                     name,
                     start_time,
                     description=None,
                     attributes=None,
                     mode=None,
                     rerun=False,
                     rerun_of=None,
                     **kwargs):
        """Start a new launch with the given parameters.

        :param name:        Launch name
        :param start_time:  Launch start time
        :param description: Launch description
        :param attributes:  Launch attributes
        :param mode:        Launch mode
        :param rerun:       Enables launch rerun mode
        :param rerun_of:    Rerun mode. Specifies launch to be re-runned.
                            Should be used with the 'rerun' option.
        """
        url = uri_join(self.base_url_v2, 'launch')
        request_payload = LaunchStartRequest(
            name=name,
            start_time=start_time,
            attributes=attributes,
            description=description,
            mode=mode,
            rerun=rerun,
            rerun_of=rerun_of or kwargs.get('rerunOf'),
            **kwargs
        ).payload
        response = HttpRequest(self.session.post,
                               url=url,
                               json=request_payload,
                               verify_ssl=self.verify_ssl).make()
        self._log_manager.launch_id = self.launch_id = response.id
        logger.debug('start_launch - ID: %s', self.launch_id)
        return self.launch_id

    def start_test_item(self,
                        name,
                        start_time,
                        item_type,
                        description=None,
                        attributes=None,
                        parameters=None,
                        parent_item_id=None,
                        has_stats=True,
                        code_ref=None,
                        retry=False,
                        **kwargs):
        """Start case/step/nested step item.

        :param name:        Name of the test item
        :param start_time:  Test item start time
        :param item_type:   Type of the test item. Allowable values: "suite",
                            "story", "test", "scenario", "step",
                            "before_class", "before_groups", "before_method",
                            "before_suite", "before_test", "after_class",
                            "after_groups", "after_method", "after_suite",
                            "after_test"
        :param attributes:  Test item attributes
        :param code_ref:    Physical location of the test item
        :param description: Test item description
        :param has_stats:   Set to False if test item is nested step
        :param parameters:  Set of parameters (for parametrized test items)
        :param retry:       Used to report retry of the test. Allowable values:
                            "True" or "False"
        """
        if parent_item_id:
            url = uri_join(self.base_url_v2, 'item', parent_item_id)
        else:
            url = uri_join(self.base_url_v2, 'item')
        request_payload = ItemStartRequest(
            name,
            start_time,
            item_type,
            self.launch_id,
            attributes=verify_value_length(attributes),
            code_ref=code_ref,
            description=description,
            has_stats=has_stats,
            parameters=parameters,
            retry=retry
        ).payload
        response = HttpRequest(self.session.post,
                               url=url,
                               json=request_payload,
                               verify_ssl=self.verify_ssl).make()
        logger.debug('start_test_item - ID: %s', response.id)
        return response.id

    def terminate(self, *args, **kwargs):
        """Call this to terminate the client."""
        self._log_manager.stop()

    def update_test_item(self, item_uuid, attributes=None, description=None):
        """Update existing test item at the Report Portal.

        :param str item_uuid:   Test item UUID returned on the item start
        :param str description: Test item description
        :param list attributes: Test item attributes
                                [{'key': 'k_name', 'value': 'k_value'}, ...]
        """
        data = {
            'description': description,
            'attributes': verify_value_length(attributes),
        }
        item_id = self.get_item_id_by_uuid(item_uuid)
        url = uri_join(self.base_url_v1, 'item', item_id, 'update')
        response = HttpRequest(self.session.put, url=url, json=data,
                               verify_ssl=self.verify_ssl).make()
        logger.debug('update_test_item - Item: %s', item_id)
        return response.message
