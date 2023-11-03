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

"""This module contains asynchronous implementations of ReportPortal Client."""

import asyncio
import logging
import ssl
import threading
import time as datetime
import warnings
from os import getenv
from typing import Union, Tuple, List, Dict, Any, Optional, Coroutine, TypeVar

import aiohttp
import certifi

# noinspection PyProtectedMember
from reportportal_client._internal.aio.http import RetryingClientSession
# noinspection PyProtectedMember
from reportportal_client._internal.aio.tasks import (BatchedTaskFactory, ThreadedTaskFactory,
                                                     TriggerTaskBatcher, BackgroundTaskList,
                                                     DEFAULT_TASK_TRIGGER_NUM, DEFAULT_TASK_TRIGGER_INTERVAL)
# noinspection PyProtectedMember
from reportportal_client._internal.local import set_current
# noinspection PyProtectedMember
from reportportal_client._internal.logs.batcher import LogBatcher
# noinspection PyProtectedMember
from reportportal_client._internal.services.statistics import async_send_event
# noinspection PyProtectedMember
from reportportal_client._internal.static.abstract import (
    AbstractBaseClass,
    abstractmethod
)
# noinspection PyProtectedMember
from reportportal_client._internal.static.defines import NOT_FOUND, NOT_SET
from reportportal_client.aio.tasks import Task
from reportportal_client.client import RP, OutputType
from reportportal_client.core.rp_issues import Issue
from reportportal_client.core.rp_requests import (LaunchStartRequest, AsyncHttpRequest, AsyncItemStartRequest,
                                                  AsyncItemFinishRequest, LaunchFinishRequest, RPFile,
                                                  AsyncRPRequestLog, AsyncRPLogBatch)
from reportportal_client.helpers import (root_uri_join, verify_value_length, await_if_necessary,
                                         agent_name_version, LifoQueue, uri_join)
from reportportal_client.logs import MAX_LOG_BATCH_PAYLOAD_SIZE
from reportportal_client.steps import StepReporter

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

_T = TypeVar('_T')

DEFAULT_TASK_TIMEOUT: float = 60.0
DEFAULT_SHUTDOWN_TIMEOUT: float = 120.0


class Client:
    """Stateless asynchronous ReportPortal Client.

    This class intentionally made to not store any data or context from ReportPortal. It provides basic
    reporting and data read functions in asynchronous manner. Use it whenever you want to handle item IDs, log
    batches, future tasks on your own.
    """

    api_v1: str
    api_v2: str
    base_url_v1: str
    base_url_v2: str
    endpoint: str
    is_skipped_an_issue: bool
    project: str
    api_key: str
    verify_ssl: Union[bool, str]
    retries: Optional[int]
    max_pool_size: int
    http_timeout: Optional[Union[float, Tuple[float, float]]]
    keepalive_timeout: Optional[float]
    mode: str
    launch_uuid_print: bool
    print_output: OutputType
    truncate_attributes: bool
    _skip_analytics: str
    _session: Optional[RetryingClientSession]
    __stat_task: Optional[asyncio.Task]

    def __init__(
            self,
            endpoint: str,
            project: str,
            *,
            api_key: str = None,
            is_skipped_an_issue: bool = True,
            verify_ssl: Union[bool, str] = True,
            retries: int = NOT_SET,
            max_pool_size: int = 50,
            http_timeout: Optional[Union[float, Tuple[float, float]]] = (10, 10),
            keepalive_timeout: Optional[float] = None,
            mode: str = 'DEFAULT',
            launch_uuid_print: bool = False,
            print_output: OutputType = OutputType.STDOUT,
            truncate_attributes: bool = True,
            **kwargs: Any
    ) -> None:
        """Initialize the class instance with arguments.

        :param endpoint:               Endpoint of the ReportPortal service.
        :param project:                Project name to report to.
        :param api_key:                Authorization API key.
        :param is_skipped_an_issue:    Option to mark skipped tests as not 'To Investigate' items on the
                                       server side.
        :param verify_ssl:             Option to skip ssl verification.
        :param retries:                Number of retry attempts to make in case of connection / server errors.
        :param max_pool_size:          Option to set the maximum number of connections to save the pool.
        :param http_timeout:           A float in seconds for connect and read timeout. Use a Tuple to
                                       specific connect and read separately.
        :param keepalive_timeout:      Maximum amount of idle time in seconds before force connection closing.
        :param mode:                   Launch mode, all Launches started by the client will be in that mode.
        :param launch_uuid_print:      Print Launch UUID into passed TextIO or by default to stdout.
        :param print_output:           Set output stream for Launch UUID printing.
        :param truncate_attributes:    Truncate test item attributes to default maximum length.
        """
        self.api_v1, self.api_v2 = 'v1', 'v2'
        self.endpoint = endpoint
        self.project = project
        self.base_url_v1 = root_uri_join(f'api/{self.api_v1}', self.project)
        self.base_url_v2 = root_uri_join(f'api/{self.api_v2}', self.project)
        self.is_skipped_an_issue = is_skipped_an_issue
        self.verify_ssl = verify_ssl
        self.retries = retries
        self.max_pool_size = max_pool_size
        self.http_timeout = http_timeout
        self.keepalive_timeout = keepalive_timeout
        self.mode = mode
        self._skip_analytics = getenv('AGENT_NO_ANALYTICS')
        self.launch_uuid_print = launch_uuid_print
        self.print_output = print_output
        self._session = None
        self.__stat_task = None
        self.api_key = api_key
        self.truncate_attributes = truncate_attributes

    async def session(self) -> RetryingClientSession:
        """Return aiohttp.ClientSession class instance, initialize it if necessary.

        :return: aiohttp.ClientSession instance.
        """
        if self._session:
            return self._session

        if self.verify_ssl is None or (type(self.verify_ssl) == bool and not self.verify_ssl):
            ssl_config = False
        else:
            if type(self.verify_ssl) is str:
                ssl_config = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH, cafile=self.verify_ssl)
            else:
                ssl_config = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH, cafile=certifi.where())

        connection_params = {
            'ssl': ssl_config,
            'limit': self.max_pool_size
        }
        if self.keepalive_timeout:
            connection_params['keepalive_timeout'] = self.keepalive_timeout
        connector = aiohttp.TCPConnector(**connection_params)

        headers = {}
        if self.api_key:
            headers['Authorization'] = f'Bearer {self.api_key}'

        session_params = {
            'headers': headers,
            'connector': connector
        }

        if self.http_timeout:
            if type(self.http_timeout) == tuple:
                connect_timeout, read_timeout = self.http_timeout
            else:
                connect_timeout, read_timeout = self.http_timeout, self.http_timeout
            session_params['timeout'] = aiohttp.ClientTimeout(connect=connect_timeout, sock_read=read_timeout)

        retries_set = self.retries is not NOT_SET and self.retries and self.retries > 0
        use_retries = self.retries is NOT_SET or (self.retries and self.retries > 0)

        if retries_set:
            session_params['max_retry_number'] = self.retries

        if use_retries:
            self._session = RetryingClientSession(self.endpoint, **session_params)
        else:
            # noinspection PyTypeChecker
            self._session = aiohttp.ClientSession(self.endpoint, **session_params)
        return self._session

    async def close(self) -> None:
        """Gracefully close internal aiohttp.ClientSession class instance and reset it."""
        if self._session:
            await self._session.close()
            self._session = None

    async def __get_item_url(self, item_id_future: Union[str, Task[str]]) -> Optional[str]:
        item_id = await await_if_necessary(item_id_future)
        if item_id is NOT_FOUND:
            logger.warning('Attempt to make request for non-existent id.')
            return
        return root_uri_join(self.base_url_v2, 'item', item_id)

    async def __get_launch_url(self, launch_uuid_future: Union[str, Task[str]]) -> Optional[str]:
        launch_uuid = await await_if_necessary(launch_uuid_future)
        if launch_uuid is NOT_FOUND:
            logger.warning('Attempt to make request for non-existent launch.')
            return
        return root_uri_join(self.base_url_v2, 'launch', launch_uuid, 'finish')

    async def start_launch(self,
                           name: str,
                           start_time: str,
                           *,
                           description: Optional[str] = None,
                           attributes: Optional[Union[list, dict]] = None,
                           rerun: bool = False,
                           rerun_of: Optional[str] = None,
                           **kwargs) -> Optional[str]:
        """Start a new Launch with the given arguments.

        :param name:        Launch name.
        :param start_time:  Launch start time.
        :param description: Launch description.
        :param attributes:  Launch attributes.
        :param rerun:       Start launch in rerun mode.
        :param rerun_of:    For rerun mode specifies which launch will be re-run. Should be used with the
                            'rerun' option.
        :return:            Launch UUID if successfully started or None.
        """
        url = root_uri_join(self.base_url_v2, 'launch')
        request_payload = LaunchStartRequest(
            name=name,
            start_time=start_time,
            attributes=verify_value_length(attributes) if self.truncate_attributes else attributes,
            description=description,
            mode=self.mode,
            rerun=rerun,
            rerun_of=rerun_of
        ).payload

        response = await AsyncHttpRequest((await self.session()).post, url=url, json=request_payload).make()
        if not response:
            return

        if not self._skip_analytics:
            stat_coro = async_send_event('start_launch', *agent_name_version(attributes))
            self.__stat_task = asyncio.create_task(stat_coro)

        launch_uuid = await response.id
        logger.debug(f'start_launch - ID: {launch_uuid}')
        if self.launch_uuid_print and self.print_output:
            print(f'ReportPortal Launch UUID: {launch_uuid}', file=self.print_output.get_output())
        return launch_uuid

    async def start_test_item(self,
                              launch_uuid: Union[str, Task[str]],
                              name: str,
                              start_time: str,
                              item_type: str,
                              *,
                              parent_item_id: Optional[Union[str, Task[str]]] = None,
                              description: Optional[str] = None,
                              attributes: Optional[Union[List[dict], dict]] = None,
                              parameters: Optional[dict] = None,
                              code_ref: Optional[str] = None,
                              test_case_id: Optional[str] = None,
                              has_stats: bool = True,
                              retry: bool = False,
                              **_: Any) -> Optional[str]:
        """Start Test Case/Suite/Step/Nested Step Item.

        :param launch_uuid:    A launch UUID where to start the Test Item.
        :param name:           Name of the Test Item.
        :param start_time:     The Item start time.
        :param item_type:      Type of the Test Item. Allowed values:
                               "suite", "story", "test", "scenario", "step", "before_class", "before_groups",
                               "before_method", "before_suite", "before_test", "after_class", "after_groups",
                               "after_method", "after_suite", "after_test".
        :param parent_item_id: A UUID of a parent SUITE / STEP.
        :param description:    The Item description.
        :param attributes:     Test Item attributes.
        :param parameters:     Set of parameters (for parametrized Test Items).
        :param code_ref:       Physical location of the Test Item.
        :param test_case_id:   A unique ID of the current Step.
        :param has_stats:      Set to False if test item is a Nested Step.
        :param retry:          Used to report retry of the test. Allowed values: "True" or "False".
        :return:               Test Item UUID if successfully started or None.
        """
        if parent_item_id:
            url = self.__get_item_url(parent_item_id)
        else:
            url = root_uri_join(self.base_url_v2, 'item')
        request_payload = AsyncItemStartRequest(
            name,
            start_time,
            item_type,
            launch_uuid,
            attributes=verify_value_length(attributes) if self.truncate_attributes else attributes,
            code_ref=code_ref,
            description=description,
            has_stats=has_stats,
            parameters=parameters,
            retry=retry,
            test_case_id=test_case_id
        ).payload

        response = await AsyncHttpRequest((await self.session()).post, url=url, json=request_payload).make()
        if not response:
            return
        item_id = await response.id
        if item_id is NOT_FOUND or item_id is None:
            logger.warning('start_test_item - invalid response: %s', str(await response.json))
        else:
            logger.debug('start_test_item - ID: %s', item_id)
        return item_id

    async def finish_test_item(self,
                               launch_uuid: Union[str, Task[str]],
                               item_id: Union[str, Task[str]],
                               end_time: str,
                               *,
                               status: str = None,
                               description: str = None,
                               attributes: Optional[Union[list, dict]] = None,
                               issue: Optional[Issue] = None,
                               retry: bool = False,
                               **kwargs: Any) -> Optional[str]:
        """Finish Test Suite/Case/Step/Nested Step Item.

        :param launch_uuid: A launch UUID where to finish the Test Item.
        :param item_id:     ID of the Test Item.
        :param end_time:    The Item end time.
        :param status:      Test status. Allowed values:
                            PASSED, FAILED, STOPPED, SKIPPED, INTERRUPTED, CANCELLED, INFO, WARN or None.
        :param description: Test Item description. Overrides description from start request.
        :param attributes:  Test Item attributes(tags). Pairs of key and value. These attributes override
                            attributes on start Test Item call.
        :param issue:       Issue which will be attached to the current Item.
        :param retry:       Used to report retry of the test. Allowed values: "True" or "False".
        :return:            Response message.
        """
        url = self.__get_item_url(item_id)
        request_payload = AsyncItemFinishRequest(
            end_time,
            launch_uuid,
            status,
            attributes=verify_value_length(attributes) if self.truncate_attributes else attributes,
            description=description,
            is_skipped_an_issue=self.is_skipped_an_issue,
            issue=issue,
            retry=retry
        ).payload
        response = await AsyncHttpRequest((await self.session()).put, url=url, json=request_payload).make()
        if not response:
            return
        message = await response.message
        logger.debug('finish_test_item - ID: %s', await await_if_necessary(item_id))
        logger.debug('response message: %s', message)
        return message

    async def finish_launch(self,
                            launch_uuid: Union[str, Task[str]],
                            end_time: str,
                            *,
                            status: str = None,
                            attributes: Optional[Union[list, dict]] = None,
                            **kwargs: Any) -> Optional[str]:
        """Finish a Launch.

        :param launch_uuid: A Launch UUID to finish.
        :param end_time:    Launch end time.
        :param status:      Launch status. Can be one of the followings:
                            PASSED, FAILED, STOPPED, SKIPPED, INTERRUPTED, CANCELLED.
        :param attributes:  Launch attributes. These attributes override attributes on Start Launch call.
        :return:            Response message or None.
        """
        url = self.__get_launch_url(launch_uuid)
        request_payload = LaunchFinishRequest(
            end_time,
            status=status,
            attributes=verify_value_length(attributes) if self.truncate_attributes else attributes,
            description=kwargs.get('description')
        ).payload
        response = await AsyncHttpRequest((await self.session()).put, url=url, json=request_payload,
                                          name='Finish Launch').make()
        if not response:
            return
        message = await response.message
        logger.debug('finish_launch - ID: %s', await await_if_necessary(launch_uuid))
        logger.debug('response message: %s', message)
        return message

    async def update_test_item(self,
                               item_uuid: Union[str, Task[str]],
                               *,
                               attributes: Optional[Union[list, dict]] = None,
                               description: Optional[str] = None) -> Optional[str]:
        """Update existing Test Item at the ReportPortal.

        :param item_uuid:   Test Item UUID returned on the item start.
        :param attributes:  Test Item attributes: [{'key': 'k_name', 'value': 'k_value'}, ...].
        :param description: Test Item description.
        :return:            Response message or None.
        """
        data = {
            'description': description,
            'attributes': verify_value_length(attributes) if self.truncate_attributes else attributes,
        }
        item_id = await self.get_item_id_by_uuid(item_uuid)
        url = root_uri_join(self.base_url_v1, 'item', item_id, 'update')
        response = await AsyncHttpRequest((await self.session()).put, url=url, json=data).make()
        if not response:
            return
        logger.debug('update_test_item - Item: %s', item_id)
        return await response.message

    async def __get_launch_uuid_url(self, launch_uuid_future: Union[str, Task[str]]) -> Optional[str]:
        launch_uuid = await await_if_necessary(launch_uuid_future)
        if launch_uuid is NOT_FOUND:
            logger.warning('Attempt to make request for non-existent Launch UUID.')
            return
        logger.debug('get_launch_info - ID: %s', launch_uuid)
        return root_uri_join(self.base_url_v1, 'launch', 'uuid', launch_uuid)

    async def get_launch_info(self, launch_uuid_future: Union[str, Task[str]]) -> Optional[dict]:
        """Get Launch information by Launch UUID.

        :param launch_uuid_future: Str or Task UUID returned on the Launch start.
        :return:                   Launch information in dictionary.
        """
        url = self.__get_launch_uuid_url(launch_uuid_future)
        response = await AsyncHttpRequest((await self.session()).get, url=url).make()
        if not response:
            return
        launch_info = None
        if response.is_success:
            launch_info = await response.json
            logger.debug('get_launch_info - Launch info: %s', launch_info)
        else:
            logger.warning('get_launch_info - Launch info: Failed to fetch launch ID from the API.')
        return launch_info

    async def __get_item_uuid_url(self, item_uuid_future: Union[str, Task[str]]) -> Optional[str]:
        item_uuid = await await_if_necessary(item_uuid_future)
        if item_uuid is NOT_FOUND:
            logger.warning('Attempt to make request for non-existent UUID.')
            return
        return root_uri_join(self.base_url_v1, 'item', 'uuid', item_uuid)

    async def get_item_id_by_uuid(self, item_uuid_future: Union[str, Task[str]]) -> Optional[str]:
        """Get Test Item ID by the given Item UUID.

        :param item_uuid_future: Str or Task UUID returned on the Item start.
        :return:                 Test Item ID.
        """
        url = self.__get_item_uuid_url(item_uuid_future)
        response = await AsyncHttpRequest((await self.session()).get, url=url).make()
        return await response.id if response else None

    async def get_launch_ui_id(self, launch_uuid_future: Union[str, Task[str]]) -> Optional[int]:
        """Get Launch ID of the given Launch.

        :param launch_uuid_future: Str or Task UUID returned on the Launch start.
        :return:                   Launch ID of the Launch. None if not found.
        """
        launch_info = await self.get_launch_info(launch_uuid_future)
        return launch_info.get('id') if launch_info else None

    async def get_launch_ui_url(self, launch_uuid_future: Union[str, Task[str]]) -> Optional[str]:
        """Get full quality URL of the given Launch.

        :param launch_uuid_future: Str or Task UUID returned on the Launch start.
        :return:                   Launch URL string.
        """
        launch_uuid = await await_if_necessary(launch_uuid_future)
        launch_info = await self.get_launch_info(launch_uuid)
        launch_id = launch_info.get('id') if launch_info else None
        if not launch_id:
            return
        mode = launch_info.get('mode') if launch_info else None
        if not mode:
            mode = self.mode

        launch_type = 'launches' if mode.upper() == 'DEFAULT' else 'userdebug'

        path = f'ui/#{self.project.lower()}/{launch_type}/all/{launch_id}'
        url = uri_join(self.endpoint, path)
        logger.debug('get_launch_ui_url - ID: %s', launch_uuid)
        return url

    async def get_project_settings(self) -> Optional[dict]:
        """Get settings of the current Project.

        :return: Settings response in Dictionary.
        """
        url = root_uri_join(self.base_url_v1, 'settings')
        response = await AsyncHttpRequest((await self.session()).get, url=url).make()
        return await response.json if response else None

    async def log_batch(self, log_batch: Optional[List[AsyncRPRequestLog]]) -> Optional[Tuple[str, ...]]:
        """Send batch logging message to the ReportPortal.

        :param log_batch: A list of log message objects.
        :return:          Completion message tuple of variable size (depending on request size).
        """
        url = root_uri_join(self.base_url_v2, 'log')
        if log_batch:
            response = await AsyncHttpRequest((await self.session()).post, url=url,
                                              data=AsyncRPLogBatch(log_batch).payload).make()
            if not response:
                return
            return await response.messages

    def clone(self) -> 'Client':
        """Clone the client object, set current Item ID as cloned item ID.

        :return: Cloned client object
        :rtype: AsyncRPClient
        """
        cloned = Client(
            endpoint=self.endpoint,
            project=self.project,
            api_key=self.api_key,
            is_skipped_an_issue=self.is_skipped_an_issue,
            verify_ssl=self.verify_ssl,
            retries=self.retries,
            max_pool_size=self.max_pool_size,
            http_timeout=self.http_timeout,
            keepalive_timeout=self.keepalive_timeout,
            mode=self.mode,
            launch_uuid_print=self.launch_uuid_print,
            print_output=self.print_output
        )
        return cloned

    def __getstate__(self) -> Dict[str, Any]:
        """Control object pickling and return object fields as Dictionary.

        :return: object state dictionary
        :rtype: dict
        """
        state = self.__dict__.copy()
        # Don't pickle 'session' field, since it contains unpickling 'socket'
        del state['_session']
        return state

    def __setstate__(self, state: Dict[str, Any]) -> None:
        """Control object pickling, receives object state as Dictionary.

        :param dict state: object state dictionary
        """
        self.__dict__.update(state)


class AsyncRPClient(RP):
    """Asynchronous ReportPortal Client.

    This class implements common RP client interface but all its methods are async, so it capable to use in
    asynchronous ReportPortal agents. It handles HTTP request and response bodies generation and
    serialization, connection retries and log batching.
    """

    log_batch_size: int
    log_batch_payload_limit: int
    _item_stack: LifoQueue
    _log_batcher: LogBatcher
    __client: Client
    __launch_uuid: Optional[str]
    __step_reporter: StepReporter
    use_own_launch: bool

    @property
    def client(self) -> Client:
        """Return current Client instance.

        :return: Client instance.
        """
        return self.__client

    @property
    def launch_uuid(self) -> Optional[str]:
        """Return current Launch UUID.

        :return: UUID string.
        """
        return self.__launch_uuid

    @property
    def endpoint(self) -> str:
        """Return current base URL.

        :return: base URL string.
        """
        return self.__endpoint

    @property
    def project(self) -> str:
        """Return current Project name.

        :return: Project name string.
        """
        return self.__project

    @property
    def step_reporter(self) -> StepReporter:
        """Return StepReporter object for the current launch.

        :return: StepReporter to report steps.
        """
        return self.__step_reporter

    def __init__(
            self,
            endpoint: str,
            project: str,
            *,
            client: Optional[Client] = None,
            launch_uuid: Optional[str] = None,
            log_batch_size: int = 20,
            log_batch_payload_limit: int = MAX_LOG_BATCH_PAYLOAD_SIZE,
            log_batcher: Optional[LogBatcher] = None,
            **kwargs: Any
    ) -> None:
        """Initialize the class instance with arguments.

        :param endpoint:                Endpoint of the ReportPortal service.
        :param project:                 Project name to report to.
        :param api_key:                 Authorization API key.
        :param is_skipped_an_issue:     Option to mark skipped tests as not 'To Investigate' items on the
                                        server side.
        :param verify_ssl:              Option to skip ssl verification.
        :param retries:                 Number of retry attempts to make in case of connection / server
                                        errors.
        :param max_pool_size:           Option to set the maximum number of connections to save the pool.
        :param http_timeout:            A float in seconds for connect and read timeout. Use a Tuple to
                                        specific connect and read separately.
        :param keepalive_timeout:       Maximum amount of idle time in seconds before force connection
                                        closing.
        :param mode:                    Launch mode, all Launches started by the client will be in that mode.
        :param launch_uuid_print:       Print Launch UUID into passed TextIO or by default to stdout.
        :param print_output:            Set output stream for Launch UUID printing.
        :param truncate_attributes:     Truncate test item attributes to default maximum length.
        :param client:                  ReportPortal async Client instance to use. If set, all above arguments
                                        will be ignored.
        :param launch_uuid:             A launch UUID to use instead of starting own one.
        :param log_batch_size:          Option to set the maximum number of logs that can be processed in one
                                        batch.
        :param log_batch_payload_limit: maximum size in bytes of logs that can be processed in one batch
        :param log_batcher:             ReportPortal log batcher instance to use. If set, 'log_batch'
                                        arguments above will be ignored.
        """
        self.__endpoint = endpoint
        self.__project = project
        self.__step_reporter = StepReporter(self)
        self._item_stack = LifoQueue()
        self.log_batch_size = log_batch_size
        self.log_batch_payload_limit = log_batch_payload_limit
        self._log_batcher = log_batcher or LogBatcher(log_batch_size, log_batch_payload_limit)
        if client:
            self.__client = client
        else:
            self.__client = Client(endpoint, project, **kwargs)
        self.__launch_uuid = launch_uuid
        if launch_uuid:
            self.use_own_launch = False
        else:
            self.use_own_launch = True
        set_current(self)

    async def start_launch(self,
                           name: str,
                           start_time: str,
                           description: Optional[str] = None,
                           attributes: Optional[Union[list, dict]] = None,
                           rerun: bool = False,
                           rerun_of: Optional[str] = None,
                           **kwargs) -> Optional[str]:
        """Start a new Launch with the given arguments.

        :param name:        Launch name.
        :param start_time:  Launch start time.
        :param description: Launch description.
        :param attributes:  Launch attributes.
        :param rerun:       Start launch in rerun mode.
        :param rerun_of:    For rerun mode specifies which launch will be re-run. Should be used with the
                            'rerun' option.
        :return:            Launch UUID if successfully started or None.
        """
        if not self.use_own_launch:
            return self.launch_uuid
        launch_uuid = await self.__client.start_launch(name, start_time, description=description,
                                                       attributes=attributes, rerun=rerun, rerun_of=rerun_of,
                                                       **kwargs)
        self.__launch_uuid = launch_uuid
        return launch_uuid

    async def start_test_item(self,
                              name: str,
                              start_time: str,
                              item_type: str,
                              description: Optional[str] = None,
                              attributes: Optional[List[dict]] = None,
                              parameters: Optional[dict] = None,
                              parent_item_id: Optional[str] = None,
                              has_stats: bool = True,
                              code_ref: Optional[str] = None,
                              retry: bool = False,
                              test_case_id: Optional[str] = None,
                              **kwargs: Any) -> Optional[str]:
        """Start Test Case/Suite/Step/Nested Step Item.

        :param name:           Name of the Test Item.
        :param start_time:     The Item start time.
        :param item_type:      Type of the Test Item. Allowed values:
                               "suite", "story", "test", "scenario", "step", "before_class", "before_groups",
                               "before_method", "before_suite", "before_test", "after_class", "after_groups",
                               "after_method", "after_suite", "after_test".
        :param description:    The Item description.
        :param attributes:     Test Item attributes.
        :param parameters:     Set of parameters (for parametrized Test Items).
        :param parent_item_id: A UUID of a parent SUITE / STEP.
        :param has_stats:      Set to False if test item is a Nested Step.
        :param code_ref:       Physical location of the Test Item.
        :param retry:          Used to report retry of the test. Allowed values: "True" or "False".
        :param test_case_id:   A unique ID of the current Step.
        :return:               Test Item UUID if successfully started or None.
        """
        item_id = await self.__client.start_test_item(self.launch_uuid, name, start_time, item_type,
                                                      description=description, attributes=attributes,
                                                      parameters=parameters, parent_item_id=parent_item_id,
                                                      has_stats=has_stats, code_ref=code_ref, retry=retry,
                                                      test_case_id=test_case_id, **kwargs)
        if item_id and item_id is not NOT_FOUND:
            logger.debug('start_test_item - ID: %s', item_id)
            self._add_current_item(item_id)
        return item_id

    async def finish_test_item(self,
                               item_id: str,
                               end_time: str,
                               status: str = None,
                               issue: Optional[Issue] = None,
                               attributes: Optional[Union[list, dict]] = None,
                               description: str = None,
                               retry: bool = False,
                               **kwargs: Any) -> Optional[str]:
        """Finish Test Suite/Case/Step/Nested Step Item.

        :param item_id:     ID of the Test Item.
        :param end_time:    The Item end time.
        :param status:      Test status. Allowed values:
                            PASSED, FAILED, STOPPED, SKIPPED, INTERRUPTED, CANCELLED, INFO, WARN or None.
        :param issue:       Issue which will be attached to the current Item.
        :param attributes:  Test Item attributes(tags). Pairs of key and value. These attributes override
                            attributes on start Test Item call.
        :param description: Test Item description. Overrides description from start request.
        :param retry:       Used to report retry of the test. Allowed values: "True" or "False".
        :return:            Response message.
        """
        result = await self.__client.finish_test_item(self.launch_uuid, item_id, end_time, status=status,
                                                      issue=issue, attributes=attributes,
                                                      description=description,
                                                      retry=retry, **kwargs)
        self._remove_current_item()
        return result

    async def finish_launch(self,
                            end_time: str,
                            status: str = None,
                            attributes: Optional[Union[list, dict]] = None,
                            **kwargs: Any) -> Optional[str]:
        """Finish a Launch.

        :param end_time:   Launch end time.
        :param status:     Launch status. Can be one of the followings:
                           PASSED, FAILED, STOPPED, SKIPPED, INTERRUPTED, CANCELLED.
        :param attributes: Launch attributes. These attributes override attributes on Start Launch call.
        :return:           Response message or None.
        """
        if self.use_own_launch:
            result = await self.__client.finish_launch(self.launch_uuid, end_time, status=status,
                                                       attributes=attributes,
                                                       **kwargs)
        else:
            result = ""
        await self.__client.log_batch(self._log_batcher.flush())
        return result

    async def update_test_item(
            self,
            item_uuid: str,
            attributes: Optional[Union[list, dict]] = None,
            description: Optional[str] = None
    ) -> Optional[str]:
        """Update existing Test Item at the ReportPortal.

        :param item_uuid:   Test Item UUID returned on the item start.
        :param attributes:  Test Item attributes: [{'key': 'k_name', 'value': 'k_value'}, ...].
        :param description: Test Item description.
        :return:            Response message or None.
        """
        return await self.__client.update_test_item(item_uuid, attributes=attributes, description=description)

    def _add_current_item(self, item: str) -> None:
        """Add the last item from the self._items queue."""
        self._item_stack.put(item)

    def _remove_current_item(self) -> Optional[str]:
        """Remove the last item from the self._items queue."""
        return self._item_stack.get()

    def current_item(self) -> Optional[str]:
        """Retrieve the last Item reported by the client (based on the internal FILO queue).

        :return: Item UUID string.
        """
        return self._item_stack.last()

    async def get_launch_info(self) -> Optional[dict]:
        """Get current Launch information.

        :return: Launch information in dictionary.
        """
        if not self.launch_uuid:
            return {}
        return await self.__client.get_launch_info(self.launch_uuid)

    async def get_item_id_by_uuid(self, item_uuid: str) -> Optional[str]:
        """Get Test Item ID by the given Item UUID.

        :param item_uuid: String UUID returned on the Item start.
        :return:          Test Item ID.
        """
        return await self.__client.get_item_id_by_uuid(item_uuid)

    async def get_launch_ui_id(self) -> Optional[int]:
        """Get Launch ID of the current Launch.

        :return: Launch ID of the Launch. None if not found.
        """
        if not self.launch_uuid:
            return
        return await self.__client.get_launch_ui_id(self.launch_uuid)

    async def get_launch_ui_url(self) -> Optional[str]:
        """Get full quality URL of the current Launch.

        :return: Launch URL string.
        """
        if not self.launch_uuid:
            return
        return await self.__client.get_launch_ui_url(self.launch_uuid)

    async def get_project_settings(self) -> Optional[dict]:
        """Get settings of the current Project.

        :return: Settings response in Dictionary.
        """
        return await self.__client.get_project_settings()

    async def log(
            self,
            time: str,
            message: str,
            level: Optional[Union[int, str]] = None,
            attachment: Optional[dict] = None,
            item_id: Optional[str] = None
    ) -> Optional[Tuple[str, ...]]:
        """Send Log message to the ReportPortal and attach it to a Test Item or Launch.

        This method stores Log messages in internal batch and sent it when batch is full, so not every method
        call will return any response.

        :param time:       Time in UTC.
        :param message:    Log message text.
        :param level:      Message's Log level.
        :param attachment: Message's attachments(images,files,etc.).
        :param item_id:    UUID of the ReportPortal Item the message belongs to.
        :return:           Response message Tuple if Log message batch was sent or None.
        """
        if item_id is NOT_FOUND:
            logger.warning("Attempt to log to non-existent item")
            return
        rp_file = RPFile(**attachment) if attachment else None
        rp_log = AsyncRPRequestLog(self.launch_uuid, time, rp_file, item_id, level, message)
        return await self.__client.log_batch(await self._log_batcher.append_async(rp_log))

    def clone(self) -> 'AsyncRPClient':
        """Clone the Client object, set current Item ID as cloned Item ID.

        :return: Cloned client object
        :rtype: AsyncRPClient.
        """
        cloned_client = self.__client.clone()
        # noinspection PyTypeChecker
        cloned = AsyncRPClient(
            endpoint=self.endpoint,
            project=self.project,
            client=cloned_client,
            launch_uuid=self.launch_uuid,
            log_batch_size=self.log_batch_size,
            log_batch_payload_limit=self.log_batch_payload_limit,
            log_batcher=self._log_batcher
        )
        current_item = self.current_item()
        if current_item:
            cloned._add_current_item(current_item)
        return cloned

    async def close(self) -> None:
        """Close current client connections."""
        await self.__client.log_batch(self._log_batcher.flush())
        await self.__client.close()


class _RPClient(RP, metaclass=AbstractBaseClass):
    """Base class for different synchronous to asynchronous client implementations."""

    __metaclass__ = AbstractBaseClass

    log_batch_size: int
    log_batch_payload_limit: int
    own_launch: bool
    own_client: bool
    _item_stack: LifoQueue
    _log_batcher: LogBatcher
    __client: Client
    __launch_uuid: Optional[Task[str]]
    __endpoint: str
    __project: str
    __step_reporter: StepReporter

    @property
    def client(self) -> Client:
        """Return current Client instance.

        :return: Client instance.
        """
        return self.__client

    @property
    def launch_uuid(self) -> Optional[Task[str]]:
        """Return current Launch UUID.

        :return: UUID string.
        """
        return self.__launch_uuid

    @property
    def endpoint(self) -> str:
        """Return current base URL.

        :return: base URL string.
        """
        return self.__endpoint

    @property
    def project(self) -> str:
        """Return current Project name.

        :return: Project name string.
        """
        return self.__project

    @property
    def step_reporter(self) -> StepReporter:
        """Return StepReporter object for the current launch.

        :return: StepReporter to report steps.
        """
        return self.__step_reporter

    def __init__(
            self,
            endpoint: str,
            project: str,
            *,
            client: Optional[Client] = None,
            launch_uuid: Optional[Task[str]] = None,
            log_batch_size: int = 20,
            log_batch_payload_limit: int = MAX_LOG_BATCH_PAYLOAD_SIZE,
            log_batcher: Optional[LogBatcher] = None,
            **kwargs: Any
    ) -> None:
        """Initialize the class instance with arguments.

        :param endpoint:                Endpoint of the ReportPortal service.
        :param project:                 Project name to report to.
        :param api_key:                 Authorization API key.
        :param is_skipped_an_issue:     Option to mark skipped tests as not 'To Investigate' items on the
                                        server side.
        :param verify_ssl:              Option to skip ssl verification.
        :param retries:                 Number of retry attempts to make in case of connection / server
                                        errors.
        :param max_pool_size:           Option to set the maximum number of connections to save the pool.
        :param http_timeout:            A float in seconds for connect and read timeout. Use a Tuple to
                                        specific connect and read separately.
        :param keepalive_timeout:       Maximum amount of idle time in seconds before force connection
                                        closing.
        :param mode:                    Launch mode, all Launches started by the client will be in that mode.
        :param launch_uuid_print:       Print Launch UUID into passed TextIO or by default to stdout.
        :param print_output:            Set output stream for Launch UUID printing.
        :param truncate_attributes:     Truncate test item attributes to default maximum length.
        :param client:                  ReportPortal async Client instance to use. If set, all above arguments
                                        will be ignored.
        :param launch_uuid:             A launch UUID to use instead of starting own one.
        :param log_batch_size:          Option to set the maximum number of logs that can be processed in one
                                        batch.
        :param log_batch_payload_limit: maximum size in bytes of logs that can be processed in one batch
        :param log_batcher:             ReportPortal log batcher instance to use. If set, 'log_batch'
                                        arguments above will be ignored.
        """
        self.__endpoint = endpoint
        self.__project = project
        self.__step_reporter = StepReporter(self)
        self._item_stack = LifoQueue()

        self.log_batch_size = log_batch_size
        self.log_batch_payload_limit = log_batch_payload_limit
        self._log_batcher = log_batcher or LogBatcher(log_batch_size, log_batch_payload_limit)

        if client:
            self.__client = client
            self.own_client = False
        else:
            self.__client = Client(endpoint, project, **kwargs)
            self.own_client = False

        self.__launch_uuid = launch_uuid
        if launch_uuid:
            self.own_launch = False
        else:
            self.own_launch = True

        set_current(self)

    @abstractmethod
    def create_task(self, coro: Coroutine[Any, Any, _T]) -> Optional[Task[_T]]:
        """Create a Task from given Coroutine.

        :param coro: Coroutine which will be used for the Task creation.
        :return:     Task instance.
        """
        raise NotImplementedError('"create_task" method is not implemented!')

    @abstractmethod
    def finish_tasks(self) -> None:
        """Ensure all pending Tasks are finished, block current Thread if necessary."""
        raise NotImplementedError('"create_task" method is not implemented!')

    def _add_current_item(self, item: Task[_T]) -> None:
        """Add the last Item to the internal FILO queue.

        :param item: Future Task of the Item UUID.
        """
        self._item_stack.put(item)

    def _remove_current_item(self) -> Task[_T]:
        """Remove the last Item from the internal FILO queue.

        :return: Future Task of the Item UUID.
        """
        return self._item_stack.get()

    def current_item(self) -> Task[_T]:
        """Retrieve the last Item reported by the client (based on the internal FILO queue).

        :return: Future Task of the Item UUID.
        """
        return self._item_stack.last()

    async def __empty_str(self):
        return ""

    async def __empty_dict(self):
        return {}

    async def __int_value(self):
        return -1

    def start_launch(self,
                     name: str,
                     start_time: str,
                     description: Optional[str] = None,
                     attributes: Optional[Union[list, dict]] = None,
                     rerun: bool = False,
                     rerun_of: Optional[str] = None,
                     **kwargs) -> Task[str]:
        """Start a new Launch with the given arguments.

        :param name:        Launch name.
        :param start_time:  Launch start time.
        :param description: Launch description.
        :param attributes:  Launch attributes.
        :param rerun:       Start launch in rerun mode.
        :param rerun_of:    For rerun mode specifies which launch will be re-run. Should be used with the
                            'rerun' option.
        :return:            Launch UUID if successfully started or None.
        """
        if not self.own_launch:
            return self.launch_uuid
        launch_uuid_coro = self.__client.start_launch(name, start_time, description=description,
                                                      attributes=attributes, rerun=rerun, rerun_of=rerun_of,
                                                      **kwargs)
        self.__launch_uuid = self.create_task(launch_uuid_coro)
        return self.launch_uuid

    def start_test_item(self,
                        name: str,
                        start_time: str,
                        item_type: str,
                        description: Optional[str] = None,
                        attributes: Optional[List[dict]] = None,
                        parameters: Optional[dict] = None,
                        parent_item_id: Optional[Task[str]] = None,
                        has_stats: bool = True,
                        code_ref: Optional[str] = None,
                        retry: bool = False,
                        test_case_id: Optional[str] = None,
                        **kwargs: Any) -> Task[str]:
        """Start Test Case/Suite/Step/Nested Step Item.

        :param name:           Name of the Test Item.
        :param start_time:     The Item start time.
        :param item_type:      Type of the Test Item. Allowed values:
                               "suite", "story", "test", "scenario", "step", "before_class", "before_groups",
                               "before_method", "before_suite", "before_test", "after_class", "after_groups",
                               "after_method", "after_suite", "after_test".
        :param description:    The Item description.
        :param attributes:     Test Item attributes.
        :param parameters:     Set of parameters (for parametrized Test Items).
        :param parent_item_id: A UUID of a parent SUITE / STEP.
        :param has_stats:      Set to False if test item is a Nested Step.
        :param code_ref:       Physical location of the Test Item.
        :param retry:          Used to report retry of the test. Allowed values: "True" or "False".
        :param test_case_id:   A unique ID of the current Step.
        :return:               Test Item UUID if successfully started or None.
        """
        item_id_coro = self.__client.start_test_item(self.launch_uuid, name, start_time, item_type,
                                                     description=description, attributes=attributes,
                                                     parameters=parameters, parent_item_id=parent_item_id,
                                                     has_stats=has_stats, code_ref=code_ref, retry=retry,
                                                     test_case_id=test_case_id, **kwargs)
        item_id_task = self.create_task(item_id_coro)
        self._add_current_item(item_id_task)
        return item_id_task

    def finish_test_item(self,
                         item_id: Task[str],
                         end_time: str,
                         status: str = None,
                         issue: Optional[Issue] = None,
                         attributes: Optional[Union[list, dict]] = None,
                         description: str = None,
                         retry: bool = False,
                         **kwargs: Any) -> Task[str]:
        """Finish Test Suite/Case/Step/Nested Step Item.

        :param item_id:     ID of the Test Item.
        :param end_time:    The Item end time.
        :param status:      Test status. Allowed values:
                            PASSED, FAILED, STOPPED, SKIPPED, INTERRUPTED, CANCELLED, INFO, WARN or None.
        :param issue:       Issue which will be attached to the current Item.
        :param attributes:  Test Item attributes(tags). Pairs of key and value. These attributes override
                            attributes on start Test Item call.
        :param description: Test Item description. Overrides description from start request.
        :param retry:       Used to report retry of the test. Allowed values: "True" or "False".
        :return:            Response message.
        """
        result_coro = self.__client.finish_test_item(self.launch_uuid, item_id, end_time, status=status,
                                                     issue=issue, attributes=attributes,
                                                     description=description,
                                                     retry=retry, **kwargs)
        result_task = self.create_task(result_coro)
        self._remove_current_item()
        return result_task

    def finish_launch(self,
                      end_time: str,
                      status: str = None,
                      attributes: Optional[Union[list, dict]] = None,
                      **kwargs: Any) -> Task[str]:
        """Finish a Launch.

        :param end_time:   Launch end time.
        :param status:     Launch status. Can be one of the followings:
                           PASSED, FAILED, STOPPED, SKIPPED, INTERRUPTED, CANCELLED.
        :param attributes: Launch attributes. These attributes override attributes on Start Launch call.
        :return:           Response message or None.
        """
        self.create_task(self.__client.log_batch(self._log_batcher.flush()))
        if self.own_launch:
            result_coro = self.__client.finish_launch(self.launch_uuid, end_time, status=status,
                                                      attributes=attributes, **kwargs)
        else:
            result_coro = self.__empty_str()

        result_task = self.create_task(result_coro)
        self.finish_tasks()
        return result_task

    def update_test_item(self,
                         item_uuid: Task[str],
                         attributes: Optional[Union[list, dict]] = None,
                         description: Optional[str] = None) -> Task:
        """Update existing Test Item at the ReportPortal.

        :param item_uuid:   Test Item UUID returned on the item start.
        :param attributes:  Test Item attributes: [{'key': 'k_name', 'value': 'k_value'}, ...].
        :param description: Test Item description.
        :return:            Response message or None.
        """
        result_coro = self.__client.update_test_item(item_uuid, attributes=attributes,
                                                     description=description)
        result_task = self.create_task(result_coro)
        return result_task

    def get_launch_info(self) -> Task[dict]:
        """Get current Launch information.

        :return: Launch information in dictionary.
        """
        if not self.launch_uuid:
            return self.create_task(self.__empty_dict())
        result_coro = self.__client.get_launch_info(self.launch_uuid)
        result_task = self.create_task(result_coro)
        return result_task

    def get_item_id_by_uuid(self, item_uuid_future: Task[str]) -> Task[str]:
        """Get Test Item ID by the given Item UUID.

        :param item_uuid_future: Str or Task UUID returned on the Item start.
        :return:                 Test Item ID.
        """
        result_coro = self.__client.get_item_id_by_uuid(item_uuid_future)
        result_task = self.create_task(result_coro)
        return result_task

    def get_launch_ui_id(self) -> Task[int]:
        """Get Launch ID of the current Launch.

        :return: Launch ID of the Launch. None if not found.
        """
        if not self.launch_uuid:
            return self.create_task(self.__int_value())
        result_coro = self.__client.get_launch_ui_id(self.launch_uuid)
        result_task = self.create_task(result_coro)
        return result_task

    def get_launch_ui_url(self) -> Task[str]:
        """Get full quality URL of the current Launch.

        :return: Launch URL string.
        """
        if not self.launch_uuid:
            return self.create_task(self.__empty_str())
        result_coro = self.__client.get_launch_ui_url(self.launch_uuid)
        result_task = self.create_task(result_coro)
        return result_task

    def get_project_settings(self) -> Task[dict]:
        """Get settings of the current Project.

        :return: Settings response in Dictionary.
        """
        result_coro = self.__client.get_project_settings()
        result_task = self.create_task(result_coro)
        return result_task

    async def _log_batch(self, log_rq: Optional[List[AsyncRPRequestLog]]) -> Optional[Tuple[str, ...]]:
        return await self.__client.log_batch(log_rq)

    async def _log(self, log_rq: AsyncRPRequestLog) -> Optional[Tuple[str, ...]]:
        return await self._log_batch(await self._log_batcher.append_async(log_rq))

    def log(self, time: str, message: str, level: Optional[Union[int, str]] = None,
            attachment: Optional[dict] = None, item_id: Optional[Task[str]] = None) -> Task[Tuple[str, ...]]:
        """Send Log message to the ReportPortal and attach it to a Test Item or Launch.

        This method stores Log messages in internal batch and sent it when batch is full, so not every method
        call will return any response.

        :param time:       Time in UTC.
        :param message:    Log message text.
        :param level:      Message's Log level.
        :param attachment: Message's attachments(images,files,etc.).
        :param item_id:    UUID of the ReportPortal Item the message belongs to.
        :return:           Response message Tuple if Log message batch was sent or None.
        """
        rp_file = RPFile(**attachment) if attachment else None
        rp_log = AsyncRPRequestLog(self.launch_uuid, time, rp_file, item_id, level, message)
        return self.create_task(self._log(rp_log))

    def close(self) -> None:
        """Close current client connections."""
        self.finish_tasks()
        if self.own_client:
            self.create_task(self.__client.close()).blocking_result()


class ThreadedRPClient(_RPClient):
    """Synchronous-asynchronous ReportPortal Client which uses background Thread to execute async coroutines.

    This class implements common RP client interface, so it capable to use in synchronous ReportPortal Agents
    if you want to achieve async performance level with synchronous code. It handles HTTP request and response
    bodies generation and serialization, connection retries and log batching.
    """

    task_timeout: float
    shutdown_timeout: float
    _task_list: BackgroundTaskList[Task[_T]]
    _task_mutex: threading.RLock
    _loop: Optional[asyncio.AbstractEventLoop]
    _thread: Optional[threading.Thread]

    def __init_task_list(self, task_list: Optional[BackgroundTaskList[Task[_T]]] = None,
                         task_mutex: Optional[threading.RLock] = None):
        if task_list:
            if not task_mutex:
                warnings.warn(
                    '"task_list" argument is set, but not "task_mutex". This usually indicates '
                    'invalid use, since "task_mutex" is used to synchronize on "task_list".',
                    RuntimeWarning,
                    3
                )
        self._task_list = task_list or BackgroundTaskList()
        self._task_mutex = task_mutex or threading.RLock()

    def __heartbeat(self):
        #  We operate on our own loop with daemon thread, so we will exit in any way when main thread exit,
        #  so we can iterate forever
        self._loop.call_at(self._loop.time() + 0.1, self.__heartbeat)

    def __init_loop(self, loop: Optional[asyncio.AbstractEventLoop] = None):
        self._thread = None
        if loop:
            self._loop = loop
        else:
            self._loop = asyncio.new_event_loop()
            self._loop.set_task_factory(ThreadedTaskFactory(self.task_timeout))
            self.__heartbeat()
            self._thread = threading.Thread(target=self._loop.run_forever, name='RP-Async-Client',
                                            daemon=True)
            self._thread.start()

    async def __return_value(self, value):
        return value

    def __init__(
            self,
            endpoint: str,
            project: str,
            *,
            task_timeout: float = DEFAULT_TASK_TIMEOUT,
            shutdown_timeout: float = DEFAULT_SHUTDOWN_TIMEOUT,
            launch_uuid: Optional[Union[str, Task[str]]] = None,
            task_list: Optional[BackgroundTaskList[Task[_T]]] = None,
            task_mutex: Optional[threading.RLock] = None,
            loop: Optional[asyncio.AbstractEventLoop] = None,
            **kwargs: Any
    ) -> None:
        """Initialize the class instance with arguments.

        :param endpoint:                Endpoint of the ReportPortal service.
        :param project:                 Project name to report to.
        :param api_key:                 Authorization API key.
        :param is_skipped_an_issue:     Option to mark skipped tests as not 'To Investigate' items on the
                                        server side.
        :param verify_ssl:              Option to skip ssl verification.
        :param retries:                 Number of retry attempts to make in case of connection / server
                                        errors.
        :param max_pool_size:           Option to set the maximum number of connections to save the pool.
        :param http_timeout:            A float in seconds for connect and read timeout. Use a Tuple to
                                        specific connect and read separately.
        :param keepalive_timeout:       Maximum amount of idle time in seconds before force connection
                                        closing.
        :param mode:                    Launch mode, all Launches started by the client will be in that mode.
        :param launch_uuid_print:       Print Launch UUID into passed TextIO or by default to stdout.
        :param print_output:            Set output stream for Launch UUID printing.
        :param truncate_attributes:     Truncate test item attributes to default maximum length.
        :param client:                  ReportPortal async Client instance to use. If set, all above arguments
                                        will be ignored.
        :param launch_uuid:             A launch UUID to use instead of starting own one.
        :param log_batch_size:          Option to set the maximum number of logs that can be processed in one
                                        batch.
        :param log_batch_payload_limit: maximum size in bytes of logs that can be processed in one batch
        :param log_batcher:             ReportPortal log batcher instance to use. If set, 'log_batch'
                                        arguments above will be ignored.
        :param task_timeout:            Time limit in seconds for a Task processing.
        :param shutdown_timeout:        Time limit in seconds for shutting down internal Tasks.
        :param task_list:               Thread-safe Task list to have one task storage for multiple Clients
                                        which guarantees their processing on Launch finish. The Client creates
                                        own Task list if this argument is None.
        :param task_mutex:              Mutex object which is responsible for synchronization of the passed
                                        task_list. The Client creates own one if this argument is None.
        :param loop:                    Event Loop which is used to process Tasks. The Client creates own one
                                        if this argument is None.
        """
        self.task_timeout = task_timeout
        self.shutdown_timeout = shutdown_timeout
        self.__init_task_list(task_list, task_mutex)
        self.__init_loop(loop)
        if type(launch_uuid) is str:
            super().__init__(endpoint, project,
                             launch_uuid=self.create_task(self.__return_value(launch_uuid)), **kwargs)
        else:
            super().__init__(endpoint, project, launch_uuid=launch_uuid, **kwargs)

    def create_task(self, coro: Coroutine[Any, Any, _T]) -> Optional[Task[_T]]:
        """Create a Task from given Coroutine.

        :param coro: Coroutine which will be used for the Task creation.
        :return:     Task instance.
        """
        if not getattr(self, '_loop', None):
            return
        result = self._loop.create_task(coro)
        with self._task_mutex:
            self._task_list.append(result)
        return result

    def finish_tasks(self):
        """Ensure all pending Tasks are finished, block current Thread if necessary."""
        shutdown_start_time = datetime.time()
        with self._task_mutex:
            tasks = self._task_list.flush()
        if tasks:
            for task in tasks:
                task.blocking_result()
                if datetime.time() - shutdown_start_time >= self.shutdown_timeout:
                    break
        logs = self._log_batcher.flush()
        if logs:
            self._loop.create_task(self._log_batch(logs)).blocking_result()

    def clone(self) -> 'ThreadedRPClient':
        """Clone the Client object, set current Item ID as cloned Item ID.

        :return: Cloned client object.
        :rtype: ThreadedRPClient
        """
        # noinspection PyTypeChecker
        cloned = ThreadedRPClient(
            endpoint=self.endpoint,
            project=self.project,
            launch_uuid=self.launch_uuid,
            client=self.client,
            log_batch_size=self.log_batch_size,
            log_batch_payload_limit=self.log_batch_payload_limit,
            log_batcher=self._log_batcher,
            task_timeout=self.task_timeout,
            shutdown_timeout=self.shutdown_timeout,
            task_mutex=self._task_mutex,
            task_list=self._task_list,
            loop=self._loop
        )
        current_item = self.current_item()
        if current_item:
            cloned._add_current_item(current_item)
        return cloned

    def __getstate__(self) -> Dict[str, Any]:
        """Control object pickling and return object fields as Dictionary.

        :return: object state dictionary
        :rtype: dict
        """
        state = self.__dict__.copy()
        # Don't pickle 'session' field, since it contains unpickling 'socket'
        del state['_task_mutex']
        del state['_loop']
        del state['_thread']
        return state

    def __setstate__(self, state: Dict[str, Any]) -> None:
        """Control object pickling, receives object state as Dictionary.

        :param dict state: object state dictionary
        """
        self.__dict__.update(state)
        self.__init_task_list(self._task_list, threading.RLock())
        self.__init_loop()


class BatchedRPClient(_RPClient):
    """Synchronous-asynchronous ReportPortal Client which uses the same Thread to execute async coroutines.

    This class implements common RP client interface, so it capable to use in synchronous ReportPortal Agents
    if you want to achieve async performance level with synchronous code. It handles HTTP request and response
    bodies generation and serialization, connection retries and log batching.
    """

    task_timeout: float
    shutdown_timeout: float
    trigger_num: int
    trigger_interval: float
    _loop: asyncio.AbstractEventLoop
    _task_mutex: threading.RLock
    _task_list: TriggerTaskBatcher[Task[_T]]
    __last_run_time: float

    def __init_task_list(self, task_list: Optional[TriggerTaskBatcher[Task[_T]]] = None,
                         task_mutex: Optional[threading.RLock] = None):
        if task_list:
            if not task_mutex:
                warnings.warn(
                    '"task_list" argument is set, but not "task_mutex". This usually indicates '
                    'invalid use, since "task_mutex" is used to synchronize on "task_list".',
                    RuntimeWarning,
                    3
                )
        self._task_list = task_list or TriggerTaskBatcher(self.trigger_num, self.trigger_interval)
        self._task_mutex = task_mutex or threading.RLock()

    def __init_loop(self, loop: Optional[asyncio.AbstractEventLoop] = None):
        if loop:
            self._loop = loop
        else:
            self._loop = asyncio.new_event_loop()
            self._loop.set_task_factory(BatchedTaskFactory())

    async def __return_value(self, value):
        return value

    def __init__(
            self,
            endpoint: str,
            project: str,
            *,
            task_timeout: float = DEFAULT_TASK_TIMEOUT,
            shutdown_timeout: float = DEFAULT_SHUTDOWN_TIMEOUT,
            launch_uuid: Optional[Union[str, Task[str]]] = None,
            task_list: Optional[TriggerTaskBatcher] = None,
            task_mutex: Optional[threading.RLock] = None,
            loop: Optional[asyncio.AbstractEventLoop] = None,
            trigger_num: int = DEFAULT_TASK_TRIGGER_NUM,
            trigger_interval: float = DEFAULT_TASK_TRIGGER_INTERVAL,
            **kwargs: Any
    ) -> None:
        """Initialize the class instance with arguments.

        :param endpoint:                Endpoint of the ReportPortal service.
        :param project:                 Project name to report to.
        :param api_key:                 Authorization API key.
        :param is_skipped_an_issue:     Option to mark skipped tests as not 'To Investigate' items on the
                                        server side.
        :param verify_ssl:              Option to skip ssl verification.
        :param retries:                 Number of retry attempts to make in case of connection / server
                                        errors.
        :param max_pool_size:           Option to set the maximum number of connections to save the pool.
        :param http_timeout:            A float in seconds for connect and read timeout. Use a Tuple to
                                        specific connect and read separately.
        :param keepalive_timeout:       Maximum amount of idle time in seconds before force connection
                                        closing.
        :param mode:                    Launch mode, all Launches started by the client will be in that mode.
        :param launch_uuid_print:       Print Launch UUID into passed TextIO or by default to stdout.
        :param print_output:            Set output stream for Launch UUID printing.
        :param truncate_attributes:     Truncate test item attributes to default maximum length.
        :param client:                  ReportPortal async Client instance to use. If set, all above arguments
                                        will be ignored.
        :param launch_uuid:             A launch UUID to use instead of starting own one.
        :param log_batch_size:          Option to set the maximum number of logs that can be processed in one
                                        batch.
        :param log_batch_payload_limit: maximum size in bytes of logs that can be processed in one batch
        :param log_batcher:             ReportPortal log batcher instance to use. If set, 'log_batch'
                                        arguments above will be ignored.
        :param task_timeout:            Time limit in seconds for a Task processing.
        :param shutdown_timeout:        Time limit in seconds for shutting down internal Tasks.
        :param task_list:               Batching Task list to have one task storage for multiple Clients
                                        which guarantees their processing on Launch finish. The Client creates
                                        own Task list if this argument is None.
        :param task_mutex:              Mutex object which is responsible for synchronization of the passed
                                        task_list. The Client creates own one if this argument is None.
        :param loop:                    Event Loop which is used to process Tasks. The Client creates own one
                                        if this argument is None.
        :param trigger_num:             Number of tasks which triggers Task batch execution.
        :param trigger_interval:        Time limit which triggers Task batch execution.
        """
        self.task_timeout = task_timeout
        self.shutdown_timeout = shutdown_timeout
        self.trigger_num = trigger_num
        self.trigger_interval = trigger_interval
        self.__init_task_list(task_list, task_mutex)
        self.__last_run_time = datetime.time()
        self.__init_loop(loop)
        if type(launch_uuid) is str:
            super().__init__(endpoint, project,
                             launch_uuid=self.create_task(self.__return_value(launch_uuid)), **kwargs)
        else:
            super().__init__(endpoint, project, launch_uuid=launch_uuid, **kwargs)

    def create_task(self, coro: Coroutine[Any, Any, _T]) -> Optional[Task[_T]]:
        """Create a Task from given Coroutine.

        :param coro: Coroutine which will be used for the Task creation.
        :return:     Task instance.
        """
        if not getattr(self, '_loop', None):
            return
        result = self._loop.create_task(coro)
        with self._task_mutex:
            tasks = self._task_list.append(result)
            if tasks:
                self._loop.run_until_complete(asyncio.wait(tasks, timeout=self.task_timeout))
        return result

    def finish_tasks(self) -> None:
        """Ensure all pending Tasks are finished, block current Thread if necessary."""
        with self._task_mutex:
            tasks = self._task_list.flush()
            if tasks:
                self._loop.run_until_complete(asyncio.wait(tasks, timeout=self.shutdown_timeout))
            logs = self._log_batcher.flush()
            if logs:
                log_task = self._loop.create_task(self._log_batch(logs))
                self._loop.run_until_complete(log_task)

    def clone(self) -> 'BatchedRPClient':
        """Clone the Client object, set current Item ID as cloned Item ID.

        :return: Cloned client object.
        :rtype: BatchedRPClient
        """
        # noinspection PyTypeChecker
        cloned = BatchedRPClient(
            endpoint=self.endpoint,
            project=self.project,
            launch_uuid=self.launch_uuid,
            client=self.client,
            log_batch_size=self.log_batch_size,
            log_batch_payload_limit=self.log_batch_payload_limit,
            log_batcher=self._log_batcher,
            task_timeout=self.task_timeout,
            shutdown_timeout=self.shutdown_timeout,
            task_list=self._task_list,
            task_mutex=self._task_mutex,
            loop=self._loop,
            trigger_num=self.trigger_num,
            trigger_interval=self.trigger_interval
        )
        current_item = self.current_item()
        if current_item:
            cloned._add_current_item(current_item)
        return cloned

    def __getstate__(self) -> Dict[str, Any]:
        """Control object pickling and return object fields as Dictionary.

        :return: object state dictionary
        :rtype: dict
        """
        state = self.__dict__.copy()
        # Don't pickle 'session' field, since it contains unpickling 'socket'
        del state['_task_mutex']
        del state['_loop']
        return state

    def __setstate__(self, state: Dict[str, Any]) -> None:
        """Control object pickling, receives object state as Dictionary.

        :param dict state: object state dictionary
        """
        self.__dict__.update(state)
        self.__init_task_list(self._task_list, threading.RLock())
        self.__init_loop()
