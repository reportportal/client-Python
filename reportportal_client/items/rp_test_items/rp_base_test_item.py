"""
This module contains functional for Base RP test items management.
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

from reportportal_client.items.rp_base_item import BaseRPItem
from reportportal_client.core.rp_requests import ItemFinishRequest
from reportportal_client.core.rp_responses import RPResponse
from reportportal_client.static.defines import NOT_FOUND


class RPBaseTestItem(BaseRPItem):

    """This model stores common attributes for RP test items."""

    def __init__(self, rp_url, session, api_version, project_name, item_name, item_type, launch_uuid, description=None,
                 attributes=None, uuid=None, code_ref=None, parameters=None, unique_id=None, retry=False):
        """
        Initialize instance attributes.

        :param rp_url:          report portal url
        :param session:         Session object
        :param api_version:     RP API version
        :param project_name:    RP project name
        :param item_name:       RP item name
        :param item_type:       Type of the test item. Allowable values: "suite",
                                "story", "test", "scenario", "step",
                                "before_class", "before_groups", "before_method",
                                "before_suite", "before_test", "after_class",
                                "after_groups", "after_method", "after_suite",
                                "after_test"
        :param launch_uuid:     Parent launch UUID
        :param description:     Test item description
        :param attributes:      Test item attributes
        :param uuid:            Test item UUID (auto generated)
        :param code_ref:        Physical location of the test item
        :param parameters:      Set of parameters (for parametrized test items)
        :param unique_id:       Test item ID (auto generated)
        :param retry:           Used to report retry of the test. Allowable values:
                                "True" or "False"
        """
        super(RPBaseTestItem, self).__init__(rp_url, session, api_version, project_name, launch_uuid)
        self.item_name = item_name
        self.item_type = item_type
        self.description = description
        self.attributes = attributes
        self.uuid = uuid
        self.code_ref = code_ref
        self.parameters = parameters
        self.unique_id = unique_id
        self.retry = retry
        self.has_stats = True
        self.child_items = list()

    @property
    def response(self):
        """Get the response object for the test item"""
        return self._response

    @response.setter
    def response(self, data):
        """Set the response object for the test item."""

        self._response = RPResponse(data)
        self.uuid = self._response.id if self._response.id is not NOT_FOUND else self.uuid

    def add_child_item(self, item):
        """
        Add new child item to the list
        :param item:    test item object
        :return:        None
        """
        self.child_items.append(item)

    def finish(self, end_time, status=None, description=None, issue=None):
        """
        Form finish request for RP test item

        :param end_time:    Test item end time
        :param status:      Test status. Allowable values: "passed",
                            "failed", "stopped", "skipped", "interrupted",
                            "cancelled"
        :param description: Test item description.
        :param issue:       Issue of the current test item
        """
        endpoint = "{rp_url}/api/{version}/{projectName}/item/{itemUuid}".format(rp_url=self.rp_url,
                                                                                 version=self.api_version,
                                                                                 projectName=self.project_name,
                                                                                 itemUuid=self.uuid)

        self.add_request(endpoint, self.session.post, ItemFinishRequest, end_time, self.launch_uuid, status,
                         attributes=self.attributes, description=description, issue=issue, retry=self.retry)
