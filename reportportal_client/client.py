"""This module contains Report Portal Client class."""

#  Copyright (c) 2023 EPAM Systems
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#  https://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License

import logging
from os import getenv

import requests
from requests.adapters import HTTPAdapter, Retry, DEFAULT_RETRIES

from ._local import set_current
from .core.rp_requests import (
    HttpRequest,
    ItemStartRequest,
    ItemFinishRequest,
    LaunchStartRequest,
    LaunchFinishRequest
)
from .helpers import uri_join, verify_value_length
from .logs.log_manager import LogManager, MAX_LOG_BATCH_PAYLOAD_SIZE
from .services.statistics import send_event
from .static.defines import NOT_FOUND
from .steps import StepReporter

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


class RPClient(object):
    """Report portal client.

    The class is supposed to use by Report Portal agents: both custom and
    official to make calls to Report Portal. It handles HTTP request and
    response bodies generation and serialization, connection retries and log
    batching.
    NOTICE: the class is not thread-safe, use new class instance for every new
    thread to avoid request/response messing and other issues.
    """

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
                 http_timeout=(10, 10),
                 log_batch_payload_size=MAX_LOG_BATCH_PAYLOAD_SIZE,
                 mode='DEFAULT',
                 **_):
        """Initialize required attributes.

        :param endpoint:               Endpoint of the report portal service
        :param project:                Project name to report to
        :param token:                  Authorization token
        :param log_batch_size:         Option to set the maximum number of
                                       logs that can be processed in one batch
        :param is_skipped_an_issue:    Option to mark skipped tests as not
                                       'To Investigate' items on the server
                                       side
        :param verify_ssl:             Option to skip ssl verification
        :param max_pool_size:          Option to set the maximum number of
                                       connections to save the pool.
        :param launch_id:              a launch id to use instead of starting
                                       own one
        :param http_timeout:           a float in seconds for connect and read
                                       timeout. Use a Tuple to specific connect
                                       and read separately.
        :param log_batch_payload_size: maximum size in bytes of logs that can
                                       be processed in one batch
        """
        set_current(self)
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
        self.log_batch_payload_size = log_batch_payload_size
        self.token = token
        self.verify_ssl = verify_ssl
        self.retries = retries
        self.max_pool_size = max_pool_size
        self.http_timeout = http_timeout
        self.session = requests.Session()
        self.step_reporter = StepReporter(self)
        self._item_stack = []
        self.mode = mode
        self._skip_analytics = getenv('AGENT_NO_ANALYTICS')

        retry_strategy = Retry(
            total=retries,
            backoff_factor=0.1,
            status_forcelist=[429, 500, 502, 503, 504]
        ) if retries else DEFAULT_RETRIES
        self.session.mount('https://', HTTPAdapter(
            max_retries=retry_strategy, pool_maxsize=max_pool_size))
        # noinspection HttpUrlsUsage
        self.session.mount('http://', HTTPAdapter(
            max_retries=retry_strategy, pool_maxsize=max_pool_size))
        self.session.headers['Authorization'] = 'bearer {0}'.format(self.token)

        self._log_manager = LogManager(
            self.endpoint, self.session, self.api_v2, self.launch_id,
            self.project, max_entry_number=log_batch_size,
            max_payload_size=log_batch_payload_size,
            verify_ssl=self.verify_ssl)

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
        if self.launch_id is NOT_FOUND or not self.launch_id:
            logger.warning("Attempt to finish non-existent launch")
            return
        url = uri_join(self.base_url_v2, 'launch', self.launch_id, 'finish')
        request_payload = LaunchFinishRequest(
            end_time,
            status=status,
            attributes=attributes,
            description=kwargs.get('description')
        ).payload
        response = HttpRequest(self.session.put, url=url, json=request_payload,
                               verify_ssl=self.verify_ssl,
                               name='Finish Launch').make()
        if not response:
            return
        logger.debug('finish_launch - ID: %s', self.launch_id)
        logger.debug('response message: %s', response.message)
        return response.message

    def finish_test_item(self,
                         item_id,
                         end_time,
                         status=None,
                         issue=None,
                         attributes=None,
                         description=None,
                         retry=False,
                         **kwargs):
        """Finish suite/case/step/nested step item.

        :param item_id:     ID of the test item
        :param end_time:    The item end time
        :param status:      Test status. Allowable values: "passed",
                            "failed", "stopped", "skipped", "interrupted",
                            "cancelled" or None
        :param attributes:  Test item attributes(tags). Pairs of key and value.
                            Override attributes on start
        :param description: Test item description. Overrides description
                            from start request.
        :param issue:       Issue of the current test item
        :param retry:       Used to report retry of the test. Allowable values:
                           "True" or "False"
        """
        if item_id is NOT_FOUND or not item_id:
            logger.warning("Attempt to finish non-existent item")
            return
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
        if not response:
            return
        self._item_stack.pop() if len(self._item_stack) > 0 else None
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
        return response.id if response else None

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
        if not response:
            return
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
        launch_info = self.get_launch_info()
        return launch_info.get('id') if launch_info else None

    def get_launch_ui_url(self):
        """Get UI URL of the current launch.

        :return: launch URL or all launches URL.
        """
        launch_info = self.get_launch_info()
        ui_id = launch_info.get('id') if launch_info else None
        if not ui_id:
            return
        mode = launch_info.get('mode') if launch_info else None
        if not mode:
            mode = self.mode

        launch_type = "launches" if mode.upper() == 'DEFAULT' else 'userdebug'

        path = 'ui/#{project_name}/{launch_type}/all/{launch_id}'.format(
            project_name=self.project.lower(), launch_type=launch_type,
            launch_id=ui_id)
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
        return response.json if response else None

    def log(self, time, message, level=None, attachment=None, item_id=None):
        """Send log message to the Report Portal.

        :param time:       Time in UTC
        :param message:    Log message text
        :param level:      Message's log level
        :param attachment: Message's attachments
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
                     rerun=False,
                     rerun_of=None,
                     **kwargs):
        """Start a new launch with the given parameters.

        :param name:        Launch name
        :param start_time:  Launch start time
        :param description: Launch description
        :param attributes:  Launch attributes
        :param rerun:       Start launch in rerun mode
        :param rerun_of:    For rerun mode specifies which launch will be
                            re-run. Should be used with the 'rerun' option.
        """
        url = uri_join(self.base_url_v2, 'launch')

        # We are moving 'mode' param to the constructor, next code for the
        # transition period only.
        my_kwargs = dict(kwargs)
        if 'mode' in my_kwargs.keys():
            mode = my_kwargs['mode']
            del my_kwargs['mode']
            if not mode:
                mode = self.mode
        else:
            mode = self.mode

        request_payload = LaunchStartRequest(
            name=name,
            start_time=start_time,
            attributes=attributes,
            description=description,
            mode=mode,
            rerun=rerun,
            rerun_of=rerun_of or kwargs.get('rerunOf'),
            **my_kwargs
        ).payload
        response = HttpRequest(self.session.post,
                               url=url,
                               json=request_payload,
                               verify_ssl=self.verify_ssl).make()
        if not response:
            return

        if not self._skip_analytics:
            agent_name, agent_version = None, None

            agent_attribute = [a for a in attributes if
                               a.get('key') == 'agent'] if attributes else []
            if len(agent_attribute) > 0 and agent_attribute[0].get('value'):
                agent_name, agent_version = agent_attribute[0]['value'].split(
                    '|')
            send_event('start_launch', agent_name, agent_version)

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
                        test_case_id=None,
                        **kwargs):
        """Start case/step/nested step item.

        :param name:           Name of the test item
        :param start_time:     The item start time
        :param item_type:      Type of the test item. Allowable values:
                               "suite", "story", "test", "scenario", "step",
                               "before_class", "before_groups",
                               "before_method", "before_suite",
                               "before_test", "after_class", "after_groups",
                               "after_method", "after_suite", "after_test"
        :param attributes:     Test item attributes
        :param code_ref:       Physical location of the test item
        :param description:    The item description
        :param has_stats:      Set to False if test item is nested step
        :param parameters:     Set of parameters (for parametrized test items)
        :param parent_item_id: An ID of a parent SUITE / STEP
        :param retry:          Used to report retry of the test. Allowable
                               values: "True" or "False"
        :param test_case_id: A unique ID of the current step
        """
        if parent_item_id is NOT_FOUND:
            logger.warning("Attempt to start item for non-existent parent "
                           "item")
            return
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
            retry=retry,
            test_case_id=test_case_id
        ).payload

        response = HttpRequest(self.session.post,
                               url=url,
                               json=request_payload,
                               verify_ssl=self.verify_ssl).make()
        if not response:
            return
        item_id = response.id
        if item_id is not NOT_FOUND:
            logger.debug('start_test_item - ID: %s', item_id)
            self._item_stack.append(item_id)
        else:
            logger.warning('start_test_item - invalid response: %s',
                           str(response.json))
        return item_id

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
        if not response:
            return
        logger.debug('update_test_item - Item: %s', item_id)
        return response.message

    def current_item(self):
        """Retrieve the last item reported by the client."""
        return self._item_stack[-1] if len(self._item_stack) > 0 else None

    def clone(self):
        """Clone the client object, set current Item ID as cloned item ID.

        :returns: Cloned client object
        :rtype: RPClient
        """
        cloned = RPClient(
            endpoint=self.endpoint,
            project=self.project,
            token=self.token,
            log_batch_size=self.log_batch_size,
            is_skipped_an_issue=self.is_skipped_an_issue,
            verify_ssl=self.verify_ssl,
            retries=self.retries,
            max_pool_size=self.max_pool_size,
            launch_id=self.launch_id,
            http_timeout=self.http_timeout,
            log_batch_payload_size=self.log_batch_payload_size,
            mode=self.mode
        )
        current_item = self.current_item()
        if current_item:
            cloned._item_stack.append(current_item)
        return cloned
