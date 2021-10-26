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
from reportportal_client.core.test_manager import TestManager
from reportportal_client.core.rp_requests import (
    HttpRequest,
    LaunchStartRequest,
    LaunchFinishRequest
)
from reportportal_client.helpers import uri_join

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
        self._test_manager = TestManager(
            self.session, self.endpoint, project, self.launch_id)

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
            end_time=end_time,
            status=status,
            attributes=attributes,
            **kwargs
        ).payload
        response = HttpRequest(self.session.put, url=url, json=request_payload,
                               verify_ssl=self.verify_ssl).make()
        logger.debug('finish_launch - ID: %s', self.launch_id)
        return response.message

    def finish_test_item(self,
                         item_id,
                         end_time,
                         status,
                         issue=None,
                         attributes=None,
                         **kwargs):
        """Finish suite/case/step/nested step item.

        :param item_id:    id of the test item
        :param end_time:   time in UTC format
        :param status:     status of the test
        :param issue:      description of an issue
        :param attributes: list of attributes
        :param kwargs:     other parameters
        :return:           json message
        """
        self._test_manager.finish_test_item(self.api_v2,
                                            item_id,
                                            end_time,
                                            status,
                                            issue=issue,
                                            attributes=attributes,
                                            **kwargs)

    def get_project_settings(self):
        """Get settings from project.

        :return: json body
        """
        url = uri_join(self.base_url_v1, 'settings')
        r = self.session.get(url=url, json={}, verify=self.verify_ssl)
        return r.json()

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
                     **kwargs
                     ):
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
            rerun_of=rerun_of,
            **kwargs
        ).payload
        response = HttpRequest(self.session.post,
                               url=url,
                               json=request_payload,
                               verify_ssl=self.verify_ssl).make()
        self._test_manager.launch_id = self.launch_id = response.id
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
                        **kwargs):
        """Start case/step/nested step item.

        :param name:            Name of test item
        :param start_time:      Test item start time
        :param item_type:       Type of test item
        :param description:     Test item description
        :param attributes:      Test item attributes
        :param parameters:      Test item parameters
        :param parent_item_id:  Parent test item UUID
        :param has_stats:       Does test item has stats or not
        :param code_ref:        Test item code reference
        """
        return self._test_manager.start_test_item(self.api_v2,
                                                  name,
                                                  start_time,
                                                  item_type,
                                                  description=description,
                                                  attributes=attributes,
                                                  parameters=parameters,
                                                  parent_uuid=parent_item_id,
                                                  has_stats=has_stats,
                                                  code_ref=code_ref,
                                                  **kwargs)

    def terminate(self, *args, **kwargs):
        """Call this to terminate the client."""
        self._log_manager.stop()
