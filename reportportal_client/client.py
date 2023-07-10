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
import sys
import warnings
from os import getenv
from typing import Union, Tuple, List, Dict, Any, Optional, TextIO

import requests
from requests.adapters import HTTPAdapter, Retry, DEFAULT_RETRIES

from ._local import set_current
from .core.rp_issues import Issue
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


class RPClient:
    """Report portal client.

    The class is supposed to use by Report Portal agents: both custom and
    official to make calls to Report Portal. It handles HTTP request and
    response bodies generation and serialization, connection retries and log
    batching.
    NOTICE: the class is not thread-safe, use new class instance for every new
    thread to avoid request/response messing and other issues.
    """

    _log_manager: LogManager = ...
    api_v1: str = ...
    api_v2: str = ...
    base_url_v1: str = ...
    base_url_v2: str = ...
    endpoint: str = ...
    is_skipped_an_issue: bool = ...
    launch_id: str = ...
    log_batch_size: int = ...
    log_batch_payload_size: int = ...
    project: str = ...
    api_key: str = ...
    verify_ssl: Union[bool, str] = ...
    retries: int = ...
    max_pool_size: int = ...
    http_timeout: Union[float, Tuple[float, float]] = ...
    session: requests.Session = ...
    step_reporter: StepReporter = ...
    mode: str = ...
    launch_uuid_print: Optional[bool] = ...
    print_output: Optional[TextIO] = ...
    _skip_analytics: str = ...
    _item_stack: List[str] = ...

    def __init__(
            self,
            endpoint: str,
            project: str,
            api_key: str = None,
            log_batch_size: int = 20,
            is_skipped_an_issue: bool = True,
            verify_ssl: bool = True,
            retries: int = None,
            max_pool_size: int = 50,
            launch_id: str = None,
            http_timeout: Union[float, Tuple[float, float]] = (10, 10),
            log_batch_payload_size: int = MAX_LOG_BATCH_PAYLOAD_SIZE,
            mode: str = 'DEFAULT',
            launch_uuid_print: bool = False,
            print_output: Optional[TextIO] = None,
            **kwargs: Any
    ) -> None:
        """Initialize required attributes.

        :param endpoint:               Endpoint of the report portal service
        :param project:                Project name to report to
        :param api_key:                Authorization API key
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
        self.verify_ssl = verify_ssl
        self.retries = retries
        self.max_pool_size = max_pool_size
        self.http_timeout = http_timeout
        self.step_reporter = StepReporter(self)
        self._item_stack = []
        self.mode = mode
        self._skip_analytics = getenv('AGENT_NO_ANALYTICS')
        self.launch_uuid_print = launch_uuid_print
        self.print_output = print_output or sys.stdout

        self.api_key = api_key
        if not self.api_key:
            if 'token' in kwargs:
                warnings.warn(
                    message='Argument `token` is deprecated since 5.3.5 and '
                            'will be subject for removing in the next major '
                            'version. Use `api_key` argument instead.',
                    category=DeprecationWarning,
                    stacklevel=2
                )
                self.api_key = kwargs['token']

            if not self.api_key:
                warnings.warn(
                    message='Argument `api_key` is `None` or empty string, '
                            'that is not supposed to happen because Report '
                            'Portal is usually requires an authorization key. '
                            'Please check your code.',
                    category=RuntimeWarning,
                    stacklevel=2
                )

        self.__init_session()
        self.__init_log_manager()

    def __init_session(self) -> None:
        retry_strategy = Retry(
            total=self.retries,
            backoff_factor=0.1,
            status_forcelist=[429, 500, 502, 503, 504]
        ) if self.retries else DEFAULT_RETRIES
        session = requests.Session()
        session.mount('https://', HTTPAdapter(
            max_retries=retry_strategy, pool_maxsize=self.max_pool_size))
        # noinspection HttpUrlsUsage
        session.mount('http://', HTTPAdapter(
            max_retries=retry_strategy, pool_maxsize=self.max_pool_size))
        if self.api_key:
            session.headers['Authorization'] = 'Bearer {0}'.format(
                self.api_key)
        self.session = session

    def __init_log_manager(self) -> None:
        self._log_manager = LogManager(
            self.endpoint, self.session, self.api_v2, self.launch_id,
            self.project, max_entry_number=self.log_batch_size,
            max_payload_size=self.log_batch_payload_size,
            verify_ssl=self.verify_ssl)

    def finish_launch(self,
                      end_time: str,
                      status: str = None,
                      attributes: Optional[Union[List, Dict]] = None,
                      **kwargs: Any) -> Optional[str]:
        """Finish launch.

        :param end_time:    Launch end time
        :param status:      Launch status. Can be one of the followings:
                            PASSED, FAILED, STOPPED, SKIPPED, RESETED,
                            CANCELLED
        :param attributes:  Launch attributes
        """
        if self.launch_id is NOT_FOUND or not self.launch_id:
            logger.warning('Attempt to finish non-existent launch')
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
                         item_id: str,
                         end_time: str,
                         status: str = None,
                         issue: Optional[Issue] = None,
                         attributes: Optional[Union[List, Dict]] = None,
                         description: str = None,
                         retry: bool = False,
                         **kwargs: Any) -> Optional[str]:
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
            logger.warning('Attempt to finish non-existent item')
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

    def get_item_id_by_uuid(self, uuid: str) -> Optional[str]:
        """Get test item ID by the given UUID.

        :param uuid: UUID returned on the item start
        :return:     Test item ID
        """
        url = uri_join(self.base_url_v1, 'item', 'uuid', uuid)
        response = HttpRequest(self.session.get, url=url,
                               verify_ssl=self.verify_ssl).make()
        return response.id if response else None

    def get_launch_info(self) -> Optional[Dict]:
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

    def get_launch_ui_id(self) -> Optional[Dict]:
        """Get UI ID of the current launch.

        :return: UI ID of the given launch. None if UI ID has not been found.
        """
        launch_info = self.get_launch_info()
        return launch_info.get('id') if launch_info else None

    def get_launch_ui_url(self) -> Optional[str]:
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

        launch_type = 'launches' if mode.upper() == 'DEFAULT' else 'userdebug'

        path = 'ui/#{project_name}/{launch_type}/all/{launch_id}'.format(
            project_name=self.project.lower(), launch_type=launch_type,
            launch_id=ui_id)
        url = uri_join(self.endpoint, path)
        logger.debug('get_launch_ui_url - ID: %s', self.launch_id)
        return url

    def get_project_settings(self) -> Optional[Dict]:
        """Get project settings.

        :return: HTTP response in dictionary
        """
        url = uri_join(self.base_url_v1, 'settings')
        response = HttpRequest(self.session.get, url=url,
                               verify_ssl=self.verify_ssl).make()
        return response.json if response else None

    def log(self, time: str, message: str, level: Optional[Union[int, str]] = None,
            attachment: Optional[Dict] = None, item_id: Optional[str] = None) -> None:
        """Send log message to the Report Portal.

        :param time:       Time in UTC
        :param message:    Log message text
        :param level:      Message's log level
        :param attachment: Message's attachments
        :param item_id:    ID of the RP item the message belongs to
        """
        self._log_manager.log(time, message, level, attachment, item_id)

    def start(self) -> None:
        """Start the client."""
        self._log_manager.start()

    def start_launch(self,
                     name: str,
                     start_time: str,
                     description: Optional[str] = None,
                     attributes: Optional[Union[List, Dict]] = None,
                     rerun: bool = False,
                     rerun_of: Optional[str] = None,
                     **kwargs) -> Optional[str]:
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
        mode = my_kwargs.get('mode')
        if 'mode' in my_kwargs:
            warnings.warn(
                message='Argument `mode` is deprecated since 5.2.5 and will be subject for removing in the '
                        'next major version. Use `mode` argument in the class constructor instead.',
                category=DeprecationWarning,
                stacklevel=2
            )
            del my_kwargs['mode']
        if not mode:
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
        if self.launch_uuid_print and self.print_output:
            print(f'Report Portal Launch UUID: {self.launch_id}', file=self.print_output)
        return self.launch_id

    def start_test_item(self,
                        name: str,
                        start_time: str,
                        item_type: str,
                        description: Optional[str] = None,
                        attributes: Optional[List[Dict]] = None,
                        parameters: Optional[Dict] = None,
                        parent_item_id: Optional[str] = None,
                        has_stats: bool = True,
                        code_ref: Optional[str] = None,
                        retry: bool = False,
                        test_case_id: Optional[str] = None,
                        **_: Any) -> Optional[str]:
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
            logger.warning('Attempt to start item for non-existent parent item.')
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

    def terminate(self, *_: Any, **__: Any) -> None:
        """Call this to terminate the client."""
        self._log_manager.stop()

    def update_test_item(self, item_uuid: str, attributes: Optional[Union[List, Dict]] = None,
                         description: Optional[str] = None) -> Optional[str]:
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

    def current_item(self) -> Optional[str]:
        """Retrieve the last item reported by the client."""
        return self._item_stack[-1] if len(self._item_stack) > 0 else None

    def clone(self) -> 'RPClient':
        """Clone the client object, set current Item ID as cloned item ID.

        :returns: Cloned client object
        :rtype: RPClient
        """
        cloned = RPClient(
            endpoint=self.endpoint,
            project=self.project,
            api_key=self.api_key,
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

    def __getstate__(self) -> Dict[str, Any]:
        """Control object pickling and return object fields as Dictionary.

        :returns: object state dictionary
        :rtype: dict
        """
        state = self.__dict__.copy()
        # Don't pickle 'session' field, since it contains unpickling 'socket'
        del state['session']
        # Don't pickle '_log_manager' field, since it uses 'session' field
        del state['_log_manager']
        return state

    def __setstate__(self, state: Dict[str, Any]) -> None:
        """Control object pickling, receives object state as Dictionary.

        :param dict state: object state dictionary
        """
        self.__dict__.update(state)
        # Restore 'session' field
        self.__init_session()
        # Restore '_log_manager' field
        self.__init_log_manager()
