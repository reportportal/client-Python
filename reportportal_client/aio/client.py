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

"""This module contains asynchronous implementation of ReportPortal Client."""

import asyncio
import logging
import ssl
import sys
import threading
import time as datetime
import warnings
from os import getenv
from typing import Union, Tuple, List, Dict, Any, Optional, TextIO, Coroutine, TypeVar

import aiohttp
import certifi

from reportportal_client import RP
# noinspection PyProtectedMember
from reportportal_client._local import set_current
from reportportal_client.aio.tasks import (Task, BatchedTaskFactory, ThreadedTaskFactory, TriggerTaskBatcher,
                                           BackgroundTaskBatcher, DEFAULT_TASK_TRIGGER_NUM,
                                           DEFAULT_TASK_TRIGGER_INTERVAL)
from reportportal_client.aio.http import RetryingClientSession
from reportportal_client.core.rp_issues import Issue
from reportportal_client.core.rp_requests import (LaunchStartRequest, AsyncHttpRequest, AsyncItemStartRequest,
                                                  AsyncItemFinishRequest, LaunchFinishRequest, RPFile,
                                                  AsyncRPRequestLog, AsyncRPLogBatch)
from reportportal_client.helpers import (root_uri_join, verify_value_length, await_if_necessary,
                                         agent_name_version, LifoQueue)
from reportportal_client.logs import MAX_LOG_BATCH_PAYLOAD_SIZE
from reportportal_client.logs.batcher import LogBatcher
from reportportal_client.services.statistics import async_send_event
from reportportal_client.static.abstract import (
    AbstractBaseClass,
    abstractmethod
)
from reportportal_client.static.defines import NOT_FOUND
from reportportal_client.steps import StepReporter

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

_T = TypeVar('_T')

DEFAULT_TASK_TIMEOUT: float = 60.0
DEFAULT_SHUTDOWN_TIMEOUT: float = 120.0


class Client:
    api_v1: str
    api_v2: str
    base_url_v1: str
    base_url_v2: str
    endpoint: str
    is_skipped_an_issue: bool
    log_batch_size: int
    log_batch_payload_size: int
    project: str
    api_key: str
    verify_ssl: Union[bool, str]
    retries: int
    max_pool_size: int
    http_timeout: Union[float, Tuple[float, float]]
    keepalive_timeout: Optional[float]
    mode: str
    launch_uuid_print: Optional[bool]
    print_output: Optional[TextIO]
    _skip_analytics: str
    __session: Optional[aiohttp.ClientSession]
    __stat_task: Optional[asyncio.Task[aiohttp.ClientResponse]]

    def __init__(
            self,
            endpoint: str,
            project: str,
            *,
            api_key: str = None,
            log_batch_size: int = 20,
            is_skipped_an_issue: bool = True,
            verify_ssl: Union[bool, str] = True,
            retries: int = None,
            max_pool_size: int = 50,
            http_timeout: Union[float, Tuple[float, float]] = (10, 10),
            keepalive_timeout: Optional[float] = None,
            log_batch_payload_size: int = MAX_LOG_BATCH_PAYLOAD_SIZE,
            mode: str = 'DEFAULT',
            launch_uuid_print: bool = False,
            print_output: Optional[TextIO] = None,
            **kwargs: Any
    ) -> None:
        self.api_v1, self.api_v2 = 'v1', 'v2'
        self.endpoint = endpoint
        self.project = project
        self.base_url_v1 = root_uri_join(f'api/{self.api_v1}', self.project)
        self.base_url_v2 = root_uri_join(f'api/{self.api_v2}', self.project)
        self.is_skipped_an_issue = is_skipped_an_issue
        self.log_batch_size = log_batch_size
        self.log_batch_payload_size = log_batch_payload_size
        self.verify_ssl = verify_ssl
        self.retries = retries
        self.max_pool_size = max_pool_size
        self.http_timeout = http_timeout
        self.keepalive_timeout = keepalive_timeout
        self.mode = mode
        self._skip_analytics = getenv('AGENT_NO_ANALYTICS')
        self.launch_uuid_print = launch_uuid_print
        self.print_output = print_output or sys.stdout
        self.__session = None
        self.__stat_task = None

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

    @property
    def session(self) -> aiohttp.ClientSession:
        if self.__session:
            return self.__session

        ssl_config = self.verify_ssl
        if ssl_config:
            if type(ssl_config) == str:
                sl_config = ssl.create_default_context()
                sl_config.load_cert_chain(ssl_config)
            else:
                ssl_config = ssl.create_default_context(cafile=certifi.where())

        params = {
            'ssl': ssl_config,
            'limit': self.max_pool_size
        }
        if self.keepalive_timeout:
            params['keepalive_timeout'] = self.keepalive_timeout
        connector = aiohttp.TCPConnector(**params)

        timeout = None
        if self.http_timeout:
            if type(self.http_timeout) == tuple:
                connect_timeout, read_timeout = self.http_timeout
            else:
                connect_timeout, read_timeout = self.http_timeout, self.http_timeout
            timeout = aiohttp.ClientTimeout(connect=connect_timeout, sock_read=read_timeout)

        headers = {}
        if self.api_key:
            headers['Authorization'] = f'Bearer {self.api_key}'
        self.__session = RetryingClientSession(self.endpoint, connector=connector, headers=headers,
                                               timeout=timeout)
        return self.__session

    async def close(self):
        if self.__session:
            await self.__session.close()
            self.__session = None

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
        url = root_uri_join(self.base_url_v2, 'launch')
        request_payload = LaunchStartRequest(
            name=name,
            start_time=start_time,
            attributes=attributes,
            description=description,
            mode=self.mode,
            rerun=rerun,
            rerun_of=rerun_of or kwargs.get('rerunOf')
        ).payload

        response = await AsyncHttpRequest(self.session.post, url=url, json=request_payload).make()
        if not response:
            return

        if not self._skip_analytics:
            stat_coro = async_send_event('start_launch', *agent_name_version(attributes))
            self.__stat_task = asyncio.create_task(stat_coro, name='Statistics update')

        launch_uuid = await response.id
        logger.debug(f'start_launch - ID: {launch_uuid}')
        if self.launch_uuid_print and self.print_output:
            print(f'ReportPortal Launch UUID: {launch_uuid}', file=self.print_output)
        return launch_uuid

    async def start_test_item(self,
                              launch_uuid: Union[str, Task[str]],
                              name: str,
                              start_time: str,
                              item_type: str,
                              *,
                              description: Optional[str] = None,
                              attributes: Optional[List[Dict]] = None,
                              parameters: Optional[Dict] = None,
                              parent_item_id: Optional[Union[str, Task[str]]] = None,
                              has_stats: bool = True,
                              code_ref: Optional[str] = None,
                              retry: bool = False,
                              test_case_id: Optional[str] = None,
                              **_: Any) -> Optional[str]:
        if parent_item_id:
            url = self.__get_item_url(parent_item_id)
        else:
            url = root_uri_join(self.base_url_v2, 'item')
        request_payload = AsyncItemStartRequest(
            name,
            start_time,
            item_type,
            launch_uuid,
            attributes=verify_value_length(attributes),
            code_ref=code_ref,
            description=description,
            has_stats=has_stats,
            parameters=parameters,
            retry=retry,
            test_case_id=test_case_id
        ).payload

        response = await AsyncHttpRequest(self.session.post, url=url, json=request_payload).make()
        if not response:
            return
        item_id = await response.id
        if item_id is NOT_FOUND:
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
                               issue: Optional[Issue] = None,
                               attributes: Optional[Union[List, Dict]] = None,
                               description: str = None,
                               retry: bool = False,
                               **kwargs: Any) -> Optional[str]:
        url = self.__get_item_url(item_id)
        request_payload = AsyncItemFinishRequest(
            end_time,
            launch_uuid,
            status,
            attributes=attributes,
            description=description,
            is_skipped_an_issue=self.is_skipped_an_issue,
            issue=issue,
            retry=retry
        ).payload
        response = await AsyncHttpRequest(self.session.put, url=url, json=request_payload).make()
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
                            attributes: Optional[Union[List, Dict]] = None,
                            **kwargs: Any) -> Optional[str]:
        url = self.__get_launch_url(launch_uuid)
        request_payload = LaunchFinishRequest(
            end_time,
            status=status,
            attributes=attributes,
            description=kwargs.get('description')
        ).payload
        response = await AsyncHttpRequest(self.session.put, url=url, json=request_payload,
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
                               attributes: Optional[Union[List, Dict]] = None,
                               description: Optional[str] = None) -> Optional[str]:
        data = {
            'description': description,
            'attributes': verify_value_length(attributes),
        }
        item_id = await self.get_item_id_by_uuid(item_uuid)
        url = root_uri_join(self.base_url_v1, 'item', item_id, 'update')
        response = await AsyncHttpRequest(self.session.put, url=url, json=data).make()
        if not response:
            return
        logger.debug('update_test_item - Item: %s', item_id)
        return await response.message

    async def __get_item_uuid_url(self, item_uuid_future: Union[str, Task[str]]) -> Optional[str]:
        item_uuid = await await_if_necessary(item_uuid_future)
        if item_uuid is NOT_FOUND:
            logger.warning('Attempt to make request for non-existent UUID.')
            return
        return root_uri_join(self.base_url_v1, 'item', 'uuid', item_uuid)

    async def get_item_id_by_uuid(self, item_uuid_future: Union[str, Task[str]]) -> Optional[str]:
        """Get test Item ID by the given Item UUID.

        :param item_uuid_future: Str or Task UUID returned on the Item start
        :return:                 Test item ID
        """
        url = self.__get_item_uuid_url(item_uuid_future)
        response = await AsyncHttpRequest(self.session.get, url=url).make()
        return response.id if response else None

    async def __get_launch_uuid_url(self, launch_uuid_future: Union[str, Task[str]]) -> Optional[str]:
        launch_uuid = await await_if_necessary(launch_uuid_future)
        if launch_uuid is NOT_FOUND:
            logger.warning('Attempt to make request for non-existent Launch UUID.')
            return
        logger.debug('get_launch_info - ID: %s', launch_uuid)
        return root_uri_join(self.base_url_v1, 'launch', 'uuid', launch_uuid)

    async def get_launch_info(self, launch_uuid_future: Union[str, Task[str]]) -> Optional[Dict]:
        """Get the launch information by Launch UUID.

        :param launch_uuid_future: Str or Task UUID returned on the Launch start
        :return dict:              Launch information in dictionary
        """
        url = self.__get_launch_uuid_url(launch_uuid_future)
        response = await AsyncHttpRequest(self.session.get, url=url).make()
        if not response:
            return
        if response.is_success:
            launch_info = await response.json
            logger.debug('get_launch_info - Launch info: %s', launch_info)
        else:
            logger.warning('get_launch_info - Launch info: Failed to fetch launch ID from the API.')
            launch_info = {}
        return launch_info

    async def get_launch_ui_id(self, launch_uuid_future: Union[str, Task[str]]) -> Optional[int]:
        launch_info = await self.get_launch_info(launch_uuid_future)
        return launch_info.get('id') if launch_info else None

    async def get_launch_ui_url(self, launch_uuid_future: Union[str, Task[str]]) -> Optional[str]:
        launch_uuid = await await_if_necessary(launch_uuid_future)
        launch_info = await self.get_launch_info(launch_uuid)
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
        url = root_uri_join(self.endpoint, path)
        logger.debug('get_launch_ui_url - ID: %s', launch_uuid)
        return url

    async def get_project_settings(self) -> Optional[Dict]:
        url = root_uri_join(self.base_url_v1, 'settings')
        response = await AsyncHttpRequest(self.session.get, url=url).make()
        return await response.json if response else None

    async def log_batch(self, log_batch: Optional[List[AsyncRPRequestLog]]) -> Tuple[str, ...]:
        url = root_uri_join(self.base_url_v2, 'log')
        if log_batch:
            response = await AsyncHttpRequest(self.session.post, url=url,
                                              data=AsyncRPLogBatch(log_batch).payload).make()
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
            log_batch_size=self.log_batch_size,
            is_skipped_an_issue=self.is_skipped_an_issue,
            verify_ssl=self.verify_ssl,
            retries=self.retries,
            max_pool_size=self.max_pool_size,
            http_timeout=self.http_timeout,
            keepalive_timeout=self.keepalive_timeout,
            log_batch_payload_size=self.log_batch_payload_size,
            mode=self.mode,
            launch_uuid_print=self.launch_uuid_print,
            print_output=self.print_output
        )
        return cloned


class AsyncRPClient(RP):
    _item_stack: LifoQueue
    _log_batcher: LogBatcher
    __client: Client
    __launch_uuid: Optional[str]
    __step_reporter: StepReporter
    use_own_launch: bool

    def __init__(self, endpoint: str, project: str, *, launch_uuid: Optional[str] = None,
                 client: Optional[Client] = None, **kwargs: Any) -> None:
        set_current(self)
        self.__endpoint = endpoint
        self.__project = project
        self.__step_reporter = StepReporter(self)
        self._item_stack = LifoQueue()
        self._log_batcher = LogBatcher()
        if client:
            self.__client = client
        else:
            self.__client = Client(endpoint, project, **kwargs)
        if launch_uuid:
            self.__launch_uuid = launch_uuid
            self.use_own_launch = False
        else:
            self.use_own_launch = True

    @property
    def launch_uuid(self) -> Optional[str]:
        return self.__launch_uuid

    @property
    def endpoint(self) -> str:
        return self.__endpoint

    @property
    def project(self) -> str:
        return self.__project

    @property
    def step_reporter(self) -> StepReporter:
        return self.__step_reporter

    async def start_launch(self,
                           name: str,
                           start_time: str,
                           description: Optional[str] = None,
                           attributes: Optional[Union[List, Dict]] = None,
                           rerun: bool = False,
                           rerun_of: Optional[str] = None,
                           **kwargs) -> Optional[str]:
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
                              *,
                              description: Optional[str] = None,
                              attributes: Optional[List[Dict]] = None,
                              parameters: Optional[Dict] = None,
                              parent_item_id: Optional[str] = None,
                              has_stats: bool = True,
                              code_ref: Optional[str] = None,
                              retry: bool = False,
                              test_case_id: Optional[str] = None,
                              **kwargs: Any) -> Optional[str]:
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
                               *,
                               status: str = None,
                               issue: Optional[Issue] = None,
                               attributes: Optional[Union[List, Dict]] = None,
                               description: str = None,
                               retry: bool = False,
                               **kwargs: Any) -> Optional[str]:
        result = await self.__client.finish_test_item(self.launch_uuid, item_id, end_time, status=status,
                                                      issue=issue, attributes=attributes,
                                                      description=description,
                                                      retry=retry, **kwargs)
        self._remove_current_item()
        return result

    async def finish_launch(self,
                            end_time: str,
                            status: str = None,
                            attributes: Optional[Union[List, Dict]] = None,
                            **kwargs: Any) -> Optional[str]:
        await self.__client.log_batch(self._log_batcher.flush())
        if not self.use_own_launch:
            return ""
        result = await self.__client.finish_launch(self.launch_uuid, end_time, status=status,
                                                   attributes=attributes,
                                                   **kwargs)
        await self.__client.close()
        return result

    async def update_test_item(self, item_uuid: str, attributes: Optional[Union[List, Dict]] = None,
                               description: Optional[str] = None) -> Optional[str]:
        return await self.__client.update_test_item(item_uuid, attributes=attributes, description=description)

    def _add_current_item(self, item: str) -> None:
        """Add the last item from the self._items queue."""
        self._item_stack.put(item)

    def _remove_current_item(self) -> Optional[str]:
        """Remove the last item from the self._items queue."""
        return self._item_stack.get()

    def current_item(self) -> Optional[str]:
        """Retrieve the last item reported by the client."""
        return self._item_stack.last()

    async def get_launch_info(self) -> Optional[dict]:
        if not self.launch_uuid:
            return {}
        return await self.__client.get_launch_info(self.launch_uuid)

    async def get_item_id_by_uuid(self, item_uuid: str) -> Optional[str]:
        return await self.__client.get_item_id_by_uuid(item_uuid)

    async def get_launch_ui_id(self) -> Optional[int]:
        if not self.launch_uuid:
            return
        return await self.__client.get_launch_ui_id(self.launch_uuid)

    async def get_launch_ui_url(self) -> Optional[str]:
        if not self.launch_uuid:
            return
        return await self.__client.get_launch_ui_url(self.launch_uuid)

    async def get_project_settings(self) -> Optional[Dict]:
        return await self.__client.get_project_settings()

    async def log(self, time: str, message: str, level: Optional[Union[int, str]] = None,
                  attachment: Optional[Dict] = None,
                  item_id: Optional[str] = None) -> Optional[Tuple[str, ...]]:
        """Log message. Can be added to test item in any state.

        :param time:    Log time
        :param message:     Log message
        :param level:       Log level
        :param attachment:  Attachments(images,files,etc.)
        :param item_id: Parent item UUID
        """
        if item_id is NOT_FOUND:
            logger.warning("Attempt to log to non-existent item")
            return
        rp_file = RPFile(**attachment) if attachment else None
        rp_log = AsyncRPRequestLog(self.launch_uuid, time, rp_file, item_id, level, message)
        return await self.__client.log_batch(await self._log_batcher.append_async(rp_log))

    def clone(self) -> 'AsyncRPClient':
        """Clone the client object, set current Item ID as cloned item ID.

        :return: Cloned client object
        :rtype: AsyncRPClient
        """
        cloned_client = self.__client.clone()
        # noinspection PyTypeChecker
        cloned = AsyncRPClient(
            endpoint=None,
            project=None,
            client=cloned_client,
            launch_uuid=self.launch_uuid
        )
        current_item = self.current_item()
        if current_item:
            cloned._add_current_item(current_item)
        return cloned


class _RPClient(RP, metaclass=AbstractBaseClass):
    __metaclass__ = AbstractBaseClass

    _item_stack: LifoQueue
    _log_batcher: LogBatcher
    _shutdown_timeout: float
    _task_timeout: float
    __client: Client
    __launch_uuid: Optional[Task[str]]
    __endpoint: str
    __project: str
    use_own_launch: bool
    __step_reporter: StepReporter

    @property
    def client(self) -> Client:
        return self.__client

    @property
    def launch_uuid(self) -> Optional[Task[str]]:
        return self.__launch_uuid

    @property
    def endpoint(self) -> str:
        return self.__endpoint

    @property
    def project(self) -> str:
        return self.__project

    @property
    def step_reporter(self) -> StepReporter:
        return self.__step_reporter

    def __init__(
            self,
            endpoint: str,
            project: str,
            *,
            launch_uuid: Optional[Task[str]] = None,
            client: Optional[Client] = None,
            log_batcher: Optional[LogBatcher] = None,
            task_timeout: float = DEFAULT_TASK_TIMEOUT,
            shutdown_timeout: float = DEFAULT_SHUTDOWN_TIMEOUT,
            **kwargs: Any
    ) -> None:
        self.__endpoint = endpoint
        self.__project = project
        self.__step_reporter = StepReporter(self)
        self._item_stack = LifoQueue()
        self._shutdown_timeout = shutdown_timeout
        self._task_timeout = task_timeout
        if log_batcher:
            self._log_batcher = log_batcher
        else:
            self._log_batcher = LogBatcher()
        if client:
            self.__client = client
        else:
            self.__client = Client(endpoint, project, **kwargs)
        if launch_uuid:
            self.__launch_uuid = launch_uuid
            self.use_own_launch = False
        else:
            self.use_own_launch = True
        set_current(self)

    @abstractmethod
    def create_task(self, coro: Coroutine[Any, Any, _T]) -> Optional[Task[_T]]:
        raise NotImplementedError('"create_task" method is not implemented!')

    @abstractmethod
    def finish_tasks(self) -> None:
        raise NotImplementedError('"create_task" method is not implemented!')

    def _add_current_item(self, item: Task[_T]) -> None:
        """Add the last item from the self._items queue."""
        self._item_stack.put(item)

    def _remove_current_item(self) -> Task[_T]:
        """Remove the last item from the self._items queue."""
        return self._item_stack.get()

    def current_item(self) -> Task[_T]:
        """Retrieve the last item reported by the client."""
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
                     attributes: Optional[Union[List, Dict]] = None,
                     rerun: bool = False,
                     rerun_of: Optional[str] = None,
                     **kwargs) -> Task[str]:
        if not self.use_own_launch:
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
                        *,
                        description: Optional[str] = None,
                        attributes: Optional[List[Dict]] = None,
                        parameters: Optional[Dict] = None,
                        parent_item_id: Optional[Task[str]] = None,
                        has_stats: bool = True,
                        code_ref: Optional[str] = None,
                        retry: bool = False,
                        test_case_id: Optional[str] = None,
                        **kwargs: Any) -> Task[str]:

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
                         *,
                         status: str = None,
                         issue: Optional[Issue] = None,
                         attributes: Optional[Union[List, Dict]] = None,
                         description: str = None,
                         retry: bool = False,
                         **kwargs: Any) -> Task[str]:
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
                      attributes: Optional[Union[List, Dict]] = None,
                      **kwargs: Any) -> Task[str]:
        self.create_task(self.__client.log_batch(self._log_batcher.flush()))
        if self.use_own_launch:
            result_coro = self.__client.finish_launch(self.launch_uuid, end_time, status=status,
                                                      attributes=attributes, **kwargs)
        else:
            result_coro = self.__empty_str()

        result_task = self.create_task(result_coro)
        self.finish_tasks()
        return result_task

    def update_test_item(self,
                         item_uuid: Task[str],
                         attributes: Optional[Union[List, Dict]] = None,
                         description: Optional[str] = None) -> Task:
        result_coro = self.__client.update_test_item(item_uuid, attributes=attributes,
                                                     description=description)
        result_task = self.create_task(result_coro)
        return result_task

    def get_launch_info(self) -> Task[dict]:
        if not self.launch_uuid:
            return self.create_task(self.__empty_dict())
        result_coro = self.__client.get_launch_info(self.launch_uuid)
        result_task = self.create_task(result_coro)
        return result_task

    def get_item_id_by_uuid(self, item_uuid_future: Task[str]) -> Task[str]:
        result_coro = self.__client.get_item_id_by_uuid(item_uuid_future)
        result_task = self.create_task(result_coro)
        return result_task

    def get_launch_ui_id(self) -> Task[int]:
        if not self.launch_uuid:
            return self.create_task(self.__int_value())
        result_coro = self.__client.get_launch_ui_id(self.launch_uuid)
        result_task = self.create_task(result_coro)
        return result_task

    def get_launch_ui_url(self) -> Task[str]:
        if not self.launch_uuid:
            return self.create_task(self.__empty_str())
        result_coro = self.__client.get_launch_ui_url(self.launch_uuid)
        result_task = self.create_task(result_coro)
        return result_task

    def get_project_settings(self) -> Task[dict]:
        result_coro = self.__client.get_project_settings()
        result_task = self.create_task(result_coro)
        return result_task

    async def _log_batch(self, log_rq: Optional[List[AsyncRPRequestLog]]) -> Optional[Tuple[str, ...]]:
        return await self.__client.log_batch(log_rq)

    async def _log(self, log_rq: AsyncRPRequestLog) -> Optional[Tuple[str, ...]]:
        return await self._log_batch(await self._log_batcher.append_async(log_rq))

    def log(self, time: str, message: str, level: Optional[Union[int, str]] = None,
            attachment: Optional[Dict] = None, item_id: Optional[Task[str]] = None) -> None:
        """Log message. Can be added to test item in any state.

        :param time:    Log time
        :param message:     Log message
        :param level:       Log level
        :param attachment:  Attachments(images,files,etc.)
        :param item_id: Parent item UUID
        """
        if item_id is NOT_FOUND:
            logger.warning("Attempt to log to non-existent item")
            return
        rp_file = RPFile(**attachment) if attachment else None
        rp_log = AsyncRPRequestLog(self.launch_uuid, time, rp_file, item_id, level, message)
        self.create_task(self._log(rp_log))
        return None

    async def _close(self):
        await self.__client.close()


class ThreadedRPClient(_RPClient):
    _loop: Optional[asyncio.AbstractEventLoop]
    __task_list: BackgroundTaskBatcher[Task[_T]]
    __task_mutex: threading.RLock
    __thread: Optional[threading.Thread]

    def __init__(
            self,
            endpoint: str,
            project: str,
            *,
            launch_uuid: Optional[Task[str]] = None,
            client: Optional[Client] = None,
            log_batcher: Optional[LogBatcher] = None,
            task_list: Optional[BackgroundTaskBatcher[Task[_T]]] = None,
            task_mutex: Optional[threading.RLock] = None,
            loop: Optional[asyncio.AbstractEventLoop] = None,
            **kwargs: Any
    ) -> None:
        super().__init__(endpoint, project, launch_uuid=launch_uuid, client=client, log_batcher=log_batcher,
                         **kwargs)
        self.__task_list = task_list or BackgroundTaskBatcher()
        self.__task_mutex = task_mutex or threading.RLock()
        self.__thread = None
        if loop:
            self._loop = loop
        else:
            self._loop = asyncio.new_event_loop()
            self._loop.set_task_factory(ThreadedTaskFactory(self._task_timeout))
            self.__heartbeat()
            self.__thread = threading.Thread(target=self._loop.run_forever, name='RP-Async-Client',
                                             daemon=True)
            self.__thread.start()

    def __heartbeat(self):
        #  We operate on our own loop with daemon thread, so we will exit in any way when main thread exit,
        #  so we can iterate forever
        self._loop.call_at(self._loop.time() + 0.1, self.__heartbeat)

    def create_task(self, coro: Coroutine[Any, Any, _T]) -> Optional[Task[_T]]:
        if not getattr(self, '_loop', None):
            return
        result = self._loop.create_task(coro)
        with self.__task_mutex:
            self.__task_list.append(result)
        return result

    def finish_tasks(self):
        shutdown_start_time = datetime.time()
        with self.__task_mutex:
            tasks = self.__task_list.flush()
        for task in tasks:
            task.blocking_result()
            if datetime.time() - shutdown_start_time >= self._shutdown_timeout:
                break
        logs = self._log_batcher.flush()
        if logs:
            self._loop.create_task(self._log_batch(logs)).blocking_result()
        self._loop.create_task(self._close()).blocking_result()

    def clone(self) -> 'ThreadedRPClient':
        """Clone the client object, set current Item ID as cloned item ID.

        :return: Cloned client object
        :rtype: ThreadedRPClient
        """
        cloned_client = self.client.clone()
        # noinspection PyTypeChecker
        cloned = ThreadedRPClient(
            endpoint=None,
            project=None,
            launch_uuid=self.launch_uuid,
            client=cloned_client,
            log_batcher=self._log_batcher,
            task_mutex=self.__task_mutex,
            task_list=self.__task_list,
            loop=self._loop
        )
        current_item = self.current_item()
        if current_item:
            cloned._add_current_item(current_item)
        return cloned


class BatchedRPClient(_RPClient):
    _loop: asyncio.AbstractEventLoop
    __task_list: TriggerTaskBatcher[Task[_T]]
    __task_mutex: threading.RLock
    __last_run_time: float
    __trigger_num: int
    __trigger_interval: float

    def __init__(
            self, endpoint: str,
            project: str,
            *,
            launch_uuid: Optional[Task[str]] = None,
            client: Optional[Client] = None,
            log_batcher: Optional[LogBatcher] = None,
            task_list: Optional[TriggerTaskBatcher] = None,
            task_mutex: Optional[threading.RLock] = None,
            loop: Optional[asyncio.AbstractEventLoop] = None,
            trigger_num: int = DEFAULT_TASK_TRIGGER_NUM,
            trigger_interval: float = DEFAULT_TASK_TRIGGER_INTERVAL,
            **kwargs: Any
    ) -> None:
        super().__init__(endpoint, project, launch_uuid=launch_uuid, client=client, log_batcher=log_batcher,
                         **kwargs)
        self.__task_list = task_list or TriggerTaskBatcher()
        self.__task_mutex = task_mutex or threading.RLock()
        self.__last_run_time = datetime.time()
        if loop:
            self._loop = loop
        else:
            self._loop = asyncio.new_event_loop()
            self._loop.set_task_factory(BatchedTaskFactory())
        self.__trigger_num = trigger_num
        self.__trigger_interval = trigger_interval

    def create_task(self, coro: Coroutine[Any, Any, _T]) -> Optional[Task[_T]]:
        if not getattr(self, '_loop', None):
            return
        result = self._loop.create_task(coro)
        with self.__task_mutex:
            tasks = self.__task_list.append(result)
            if tasks:
                self._loop.run_until_complete(asyncio.wait(tasks, timeout=self._task_timeout))
        return result

    def finish_tasks(self) -> None:
        with self.__task_mutex:
            tasks = self.__task_list.flush()
            if tasks:
                self._loop.run_until_complete(asyncio.wait(tasks, timeout=self._shutdown_timeout))
            logs = self._log_batcher.flush()
            if logs:
                log_task = self._loop.create_task(self._log_batch(logs))
                self._loop.run_until_complete(log_task)
            self._loop.run_until_complete(self._close())

    def clone(self) -> 'BatchedRPClient':
        """Clone the client object, set current Item ID as cloned item ID.

        :return: Cloned client object
        :rtype: BatchedRPClient
        """
        cloned_client = self.client.clone()
        # noinspection PyTypeChecker
        cloned = BatchedRPClient(
            endpoint=None,
            project=None,
            launch_uuid=self.launch_uuid,
            client=cloned_client,
            log_batcher=self._log_batcher,
            task_list=self.__task_list,
            task_mutex=self.__task_mutex,
            loop=self._loop
        )
        current_item = self.current_item()
        if current_item:
            cloned._add_current_item(current_item)
        return cloned
