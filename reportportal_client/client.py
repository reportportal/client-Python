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

from reportportal_client.core.rp_requests import (
    HttpRequest,
    LaunchStartRequest,
    LaunchFinishRequest
)
from reportportal_client.core.test_manager import TestManager
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
                 ):
        """Initialize required attributes.

        :param endpoint:                Endpoint of report portal service
        :param project:                 Project name to use for launch names
        :param token:                   authorization token.
        :param log_batch_size:          option to set the maximum number of
                                        logs
                                        that can be processed in one batch
        :param is_skipped_an_issue:     option to mark skipped tests as not
                                        'To Investigate' items on Server side.
        :param verify_ssl:              option to not verify ssl certificates
        :param max_pool_size:           option to set the maximum number of
                                        connections to save in the pool.
        """
        self._batch_logs = []
        self.endpoint = endpoint
        self.log_batch_size = log_batch_size
        self.project = project
        self.token = token
        self.launch_id = launch_id
        self.verify_ssl = verify_ssl
        self.is_skipped_an_issue = is_skipped_an_issue

        self.api_v1 = 'v1'
        self.api_v2 = 'v2'
        self.base_url_v1 = uri_join(self.endpoint,
                                    "api/{}".format(self.api_v1),
                                    self.project)
        self.base_url_v2 = uri_join(self.endpoint,
                                    "api/{}".format(self.api_v2),
                                    self.project)

        self.session = requests.Session()
        if retries:
            self.session.mount('https://', HTTPAdapter(
                max_retries=retries, pool_maxsize=max_pool_size))
            self.session.mount('http://', HTTPAdapter(
                max_retries=retries, pool_maxsize=max_pool_size))
        self.session.headers["Authorization"] = "bearer {0}".format(self.token)

        self._test_manager = TestManager(self.session,
                                         self.endpoint,
                                         project,
                                         self.launch_id)

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

        :param name:        Name of launch
        :param start_time:  Launch start time
        :param description: Launch description
        :param attributes:  Launch attributes
        :param mode:        Launch mode
        :param rerun:       Launch rerun
        :param rerun_of:    Items to rerun in launch
        """
        url = uri_join(self.base_url_v2, "launch")

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
                               verify=self.verify_ssl).make()
        self._test_manager.launch_id = self.launch_id = response.id
        logger.debug("start_launch - ID: %s", self.launch_id)
        return self.launch_id

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
        url = uri_join(self.base_url_v2, "launch", self.launch_id, "finish")

        request_payload = LaunchFinishRequest(
            end_time=end_time,
            status=status,
            attributes=attributes,
            **kwargs
        ).payload

        response = HttpRequest(self.session.put, url=url, json=request_payload,
                               verify=self.verify_ssl).make()

        logger.debug("finish_launch - ID: %s", self.launch_id)
        return response.message

    def start_item(self,
                   name,
                   start_time,
                   item_type,
                   description=None,
                   attributes=None,
                   parameters=None,
                   parent_item_id=None,
                   has_stats=True,
                   code_ref=None,
                   **kwargs
                   ):
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
                                                  attributes=attributes[0],
                                                  parameters=parameters,
                                                  parent_uuid=parent_item_id,
                                                  has_stats=has_stats,
                                                  code_ref=code_ref,
                                                  **kwargs)

    def finish_item(self,
                    item_id,
                    end_time,
                    status,
                    issue=None,
                    attributes=None,
                    **kwargs
                    ):
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
                                            attributes=attributes[0],
                                            **kwargs)

    def save_log(self, log_time, **kwargs):
        """Save logs for test items.

        :param log_time:    Log time
        """
        pass
