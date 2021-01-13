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
from typing import Any, Optional, Dict, List

import requests
from requests.adapters import HTTPAdapter

from reportportal_client.core.test_manager import TestManager
from reportportal_client.helpers import uri_join, dict_to_payload, get_id, get_msg

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


class RPClient(object):
    """Report portal client."""

    def __init__(self,
                 endpoint,  # type: str
                 project,  # type: str
                 token,  # type: str
                 log_batch_size=20,  # type: int
                 is_skipped_an_issue=True,  # type: bool
                 verify_ssl=True,  # type: bool
                 retries=None,  # type: Optional[int]
                 max_pool_size=50,  # type: int
                 launch_id=None,  # type: Optional[str]
                 ):
        # type: (...) -> None
        """Initialize required attributes.

        :param endpoint:                Endpoint of report portal service
        :param project:                 Project name to use for launch names
        :param token:                   authorization token.
        :param log_batch_size:          option to set the maximum number of logs
                                        that can be processed in one batch
        :param is_skipped_an_issue:     option to mark skipped tests as not
                                        'To Investigate' items on Server side.
        :param verify_ssl:              option to not verify ssl certificates
        :param max_pool_size:           option to set the maximum number of connections to save in the pool.
        """
        self._batch_logs = []  # type: List
        self.endpoint = endpoint  # type: str
        self.log_batch_size = log_batch_size  # type: int
        self.project = project  # type: str
        self.token = token  # type: str
        self.launch_id = launch_id  # type: Optional[str]
        self.verify_ssl = verify_ssl  # type: bool
        self.is_skipped_an_issue = is_skipped_an_issue  # type: bool

        self.api_v1 = 'v1'
        self.api_v2 = 'v2'
        self.base_url_v1 = uri_join(self.endpoint, f"api/{self.api_v1}", self.project)  # type: str
        self.base_url_v2 = uri_join(self.endpoint, f"api/{self.api_v2}", self.project)  # type: str

        self.session = requests.Session()  # type: requests.Session
        if retries:
            self.session.mount('https://', HTTPAdapter(
                max_retries=retries, pool_maxsize=max_pool_size))
            self.session.mount('http://', HTTPAdapter(
                max_retries=retries, pool_maxsize=max_pool_size))
        self.session.headers["Authorization"] = "bearer {0}".format(self.token)

        self._test_manager = TestManager(self.session,
                                         self.endpoint,
                                         project,
                                         self.launch_id)  # type: TestManager

    def start_launch(self,
                     name,  # type: str
                     start_time,  # type: str
                     description=None,  # type: Optional[str]
                     attributes=None,  # type: Optional[Dict]
                     mode=None,  # type: Optional[str]
                     rerun=False,  # type: bool
                     rerun_of=None,  # type: Optional[List]
                     **kwargs  # type: Any
                     ):
        # type: (...) -> str
        """Start a new launch with the given parameters.

        :param name:        Name of launch
        :param start_time:  Launch start time
        :param description: Launch description
        :param attributes:  Launch attributes
        :param mode:        Launch mode
        :param rerun:       Launch rerun
        :param rerun_of:    Items to rerun in launch
        """

        if attributes and isinstance(attributes, dict):
            attributes = dict_to_payload(attributes)
        data = {
            "name": name,
            "description": description,
            "attributes": attributes,
            "startTime": start_time,
            "mode": mode,
            "rerun": rerun,
            "rerunOf": rerun_of
        }
        data.update(kwargs)
        url = uri_join(self.base_url_v2, "launch")
        response = self.session.post(url=url, json=data, verify=self.verify_ssl)
        self.launch_id = get_id(response)
        # Set launch id for test manager
        self._test_manager.launch_id = self.launch_id
        logger.debug("start_launch - ID: %s", self.launch_id)
        return self.launch_id

    def finish_launch(self, end_time, status=None, attributes=None, **kwargs):
        # type: (str, Optional[str], Optional[Dict], Any) -> Dict
        """Finish launch.

        :param end_time:    Launch end time
        :param status:      Launch status. Can be one of the followings:
                            PASSED, FAILED, STOPPED, SKIPPED, RESETED, CANCELLED
        :param attributes:  Launch attributes
        """
        # process log batches firstly:
        if attributes and isinstance(attributes, dict):
            attributes = dict_to_payload(attributes)
        data = {
            "endTime": end_time,
            "status": status,
            "attributes": attributes
        }
        data.update(kwargs)
        url = uri_join(self.base_url_v2, "launch", self.launch_id, "finish")
        response = self.session.put(url=url, json=data, verify=self.verify_ssl)
        logger.debug("finish_launch - ID: %s", self.launch_id)
        return get_msg(response)

    def start_item(self,
                   name,  # type: str
                   start_time,  # type: str
                   item_type,  # type: str
                   description=None,  # type: Optional[str]
                   attributes=None,  # type: Optional[Dict]
                   parameters=None,  # type: Optional[Dict]
                   parent_item_id=None,  # type: Optional[str]
                   has_stats=True,  # type: bool
                   code_ref=None,  # type: Optional[str]
                   **kwargs  # type: Any
                   ):
        # type: (...) -> str
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

    def finish_item(self,
                    item_id,  # type: str
                    end_time,  # type: str
                    status,  # type: str
                    issue=None,  # type: Optional[str]
                    attributes=None,  # type: Optional[Dict]
                    **kwargs  # type: Any
                    ):
        # type: (...) -> None
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

    def save_log(self, log_time, **kwargs):
        """Save logs for test items.

        :param log_time:    Log time
        """
        pass
