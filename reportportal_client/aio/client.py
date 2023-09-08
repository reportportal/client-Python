"""This module contains asynchronous implementation of Report Portal Client."""

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

import asyncio
import logging
import ssl
import sys
import threading
import time
import warnings
from os import getenv
from queue import LifoQueue
from typing import Union, Tuple, List, Dict, Any, Optional, TextIO

import aiohttp
import certifi

# noinspection PyProtectedMember
from reportportal_client._local import set_current
from reportportal_client.core.rp_issues import Issue
from reportportal_client.core.rp_requests import (LaunchStartRequest, AsyncHttpRequest, AsyncItemStartRequest,
                                                  AsyncItemFinishRequest, LaunchFinishRequest)
from reportportal_client.helpers import (root_uri_join, verify_value_length, await_if_necessary,
                                         agent_name_version)
from reportportal_client.logs import MAX_LOG_BATCH_PAYLOAD_SIZE
from reportportal_client.services.statistics import async_send_event
from reportportal_client.static.abstract import (
    AbstractBaseClass,
    abstractmethod
)
from reportportal_client.static.defines import NOT_FOUND
from reportportal_client.steps import StepReporter

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

TASK_TIMEOUT: int = 60
SHUTDOWN_TIMEOUT: int = 120


class _LifoQueue(LifoQueue):
    def last(self):
        with self.mutex:
            if self._qsize():
                return self.queue[-1]


class _AsyncRPClient:
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
    mode: str
    launch_uuid_print: Optional[bool]
    print_output: Optional[TextIO]
    _skip_analytics: str
    __session: Optional[aiohttp.ClientSession]
    __stat_task: Optional[asyncio.Task]

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
        # TODO: add retry handler
        if self.__session:
            return self.__session

        ssl_config = self.verify_ssl
        if ssl_config:
            if type(ssl_config) == str:
                sl_config = ssl.create_default_context()
                sl_config.load_cert_chain(ssl_config)
            else:
                ssl_config = ssl.create_default_context(cafile=certifi.where())

        connector = aiohttp.TCPConnector(ssl=ssl_config, limit=self.max_pool_size)

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
        self.__session = aiohttp.ClientSession(self.endpoint, connector=connector, headers=headers,
                                               timeout=timeout)
        return self.__session

    async def __get_item_url(self, item_id_future: Union[str, asyncio.Task]) -> Optional[str]:
        item_id = await await_if_necessary(item_id_future)
        if item_id is NOT_FOUND:
            logger.warning('Attempt to make request for non-existent id.')
            return
        return root_uri_join(self.base_url_v2, 'item', item_id)

    async def __get_launch_url(self, launch_uuid_future: Union[str, asyncio.Task]) -> Optional[str]:
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
        logger.debug(f'start_launch - ID: %s', launch_uuid)
        if self.launch_uuid_print and self.print_output:
            print(f'Report Portal Launch UUID: {launch_uuid}', file=self.print_output)
        return launch_uuid

    async def start_test_item(self,
                              launch_uuid: Union[str, asyncio.Task],
                              name: str,
                              start_time: str,
                              item_type: str,
                              *,
                              description: Optional[str] = None,
                              attributes: Optional[List[Dict]] = None,
                              parameters: Optional[Dict] = None,
                              parent_item_id: Optional[Union[str, asyncio.Task]] = None,
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
                               launch_uuid: Union[str, asyncio.Task],
                               item_id: Union[str, asyncio.Task],
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
                            launch_uuid: Union[str, asyncio.Task],
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
                               item_uuid: Union[str, asyncio.Task],
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

    async def __get_item_uuid_url(self, item_uuid_future: Union[str, asyncio.Task]) -> Optional[str]:
        item_uuid = await await_if_necessary(item_uuid_future)
        if item_uuid is NOT_FOUND:
            logger.warning('Attempt to make request for non-existent UUID.')
            return
        return root_uri_join(self.base_url_v1, 'item', 'uuid', item_uuid)

    async def get_item_id_by_uuid(self, item_uuid_future: Union[str, asyncio.Task]) -> Optional[str]:
        """Get test Item ID by the given Item UUID.

        :param item_uuid_future: Str or asyncio.Task UUID returned on the Item start
        :return:                 Test item ID
        """
        url = self.__get_item_uuid_url(item_uuid_future)
        response = await AsyncHttpRequest(self.session.get, url=url).make()
        return response.id if response else None

    async def __get_launch_uuid_url(self, launch_uuid_future: Union[str, asyncio.Task]) -> Optional[str]:
        launch_uuid = await await_if_necessary(launch_uuid_future)
        if launch_uuid is NOT_FOUND:
            logger.warning('Attempt to make request for non-existent Launch UUID.')
            return
        logger.debug('get_launch_info - ID: %s', launch_uuid)
        return root_uri_join(self.base_url_v1, 'launch', 'uuid', launch_uuid)

    async def get_launch_info(self, launch_uuid_future: Union[str, asyncio.Task]) -> Optional[Dict]:
        """Get the launch information by Launch UUID.

        :param launch_uuid_future: Str or asyncio.Task UUID returned on the Launch start
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

    async def get_launch_ui_id(self, launch_uuid_future: Union[str, asyncio.Task]) -> Optional[int]:
        launch_info = await self.get_launch_info(launch_uuid_future)
        return launch_info.get('id') if launch_info else None

    async def get_launch_ui_url(self, launch_uuid_future: Union[str, asyncio.Task]) -> Optional[str]:
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

    async def log(self,
                  launch_uuid: Union[str, asyncio.Task],
                  time: str,
                  message: str,
                  *,
                  level: Optional[Union[int, str]] = None,
                  attachment: Optional[Dict] = None,
                  item_id: Optional[Union[str, asyncio.Task]] = None) -> None:
        pass

    def clone(self) -> '_AsyncRPClient':
        """Clone the client object, set current Item ID as cloned item ID.

        :returns: Cloned client object
        :rtype: AsyncRPClient
        """
        cloned = _AsyncRPClient(
            endpoint=self.endpoint,
            project=self.project,
            api_key=self.api_key,
            log_batch_size=self.log_batch_size,
            is_skipped_an_issue=self.is_skipped_an_issue,
            verify_ssl=self.verify_ssl,
            retries=self.retries,
            max_pool_size=self.max_pool_size,
            http_timeout=self.http_timeout,
            log_batch_payload_size=self.log_batch_payload_size,
            mode=self.mode
        )
        return cloned


class RPClient(metaclass=AbstractBaseClass):
    __metaclass__ = AbstractBaseClass

    @abstractmethod
    def start_launch(self,
                     name: str,
                     start_time: str,
                     description: Optional[str] = None,
                     attributes: Optional[Union[List, Dict]] = None,
                     rerun: bool = False,
                     rerun_of: Optional[str] = None,
                     **kwargs) -> Union[Optional[str], asyncio.Task]:
        raise NotImplementedError('"start_launch" method is not implemented!')

    @abstractmethod
    def start_test_item(self,
                        name: str,
                        start_time: str,
                        item_type: str,
                        *,
                        description: Optional[str] = None,
                        attributes: Optional[List[Dict]] = None,
                        parameters: Optional[Dict] = None,
                        parent_item_id: Union[Optional[str], asyncio.Task] = None,
                        has_stats: bool = True,
                        code_ref: Optional[str] = None,
                        retry: bool = False,
                        test_case_id: Optional[str] = None,
                        **kwargs: Any) -> Union[Optional[str], asyncio.Task]:
        raise NotImplementedError('"start_test_item" method is not implemented!')

    @abstractmethod
    def finish_test_item(self,
                         item_id: Union[str, asyncio.Task],
                         end_time: str,
                         *,
                         status: str = None,
                         issue: Optional[Issue] = None,
                         attributes: Optional[Union[List, Dict]] = None,
                         description: str = None,
                         retry: bool = False,
                         **kwargs: Any) -> Union[Optional[str], asyncio.Task]:
        raise NotImplementedError('"finish_test_item" method is not implemented!')

    @abstractmethod
    def finish_launch(self,
                      end_time: str,
                      status: str = None,
                      attributes: Optional[Union[List, Dict]] = None,
                      **kwargs: Any) -> Union[Optional[str], asyncio.Task]:
        raise NotImplementedError('"finish_launch" method is not implemented!')

    @abstractmethod
    def update_test_item(self, item_uuid: str, attributes: Optional[Union[List, Dict]] = None,
                         description: Optional[str] = None) -> Optional[str]:
        raise NotImplementedError('"update_test_item" method is not implemented!')

    @abstractmethod
    def get_launch_info(self) -> Union[Optional[dict], asyncio.Task]:
        raise NotImplementedError('"get_launch_info" method is not implemented!')

    @abstractmethod
    def get_item_id_by_uuid(self, item_uuid: str) -> Optional[str]:
        raise NotImplementedError('"get_item_id_by_uuid" method is not implemented!')

    @abstractmethod
    def get_launch_ui_id(self) -> Optional[int]:
        raise NotImplementedError('"get_launch_ui_id" method is not implemented!')

    @abstractmethod
    def get_launch_ui_url(self) -> Optional[str]:
        raise NotImplementedError('"get_launch_ui_id" method is not implemented!')

    @abstractmethod
    def get_project_settings(self) -> Optional[Dict]:
        raise NotImplementedError('"get_project_settings" method is not implemented!')

    @abstractmethod
    def log(self, time: str, message: str, level: Optional[Union[int, str]] = None,
            attachment: Optional[Dict] = None, item_id: Optional[str] = None) -> None:
        raise NotImplementedError('"log" method is not implemented!')

    def start(self) -> None:
        pass  # For backward compatibility

    def terminate(self, *_: Any, **__: Any) -> None:
        pass  # For backward compatibility


class AsyncRPClient(RPClient):
    __client: _AsyncRPClient
    _item_stack: _LifoQueue
    launch_uuid: Optional[str]
    use_own_launch: bool
    step_reporter: StepReporter

    def __init__(self, endpoint: str, project: str, *, launch_uuid: Optional[str] = None,
                 client: Optional[_AsyncRPClient] = None, **kwargs: Any) -> None:
        set_current(self)
        self.step_reporter = StepReporter(self)
        self._item_stack = _LifoQueue()
        if client:
            self.__client = client
        else:
            self.__client = _AsyncRPClient(endpoint, project, **kwargs)
        if launch_uuid:
            self.launch_uuid = launch_uuid
            self.use_own_launch = False
        else:
            self.use_own_launch = True

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
        self.launch_uuid = launch_uuid
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
                               item_id: Union[asyncio.Task, str],
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
        if not self.use_own_launch:
            return ""
        return await self.__client.finish_launch(self.launch_uuid, end_time, status=status,
                                                 attributes=attributes,
                                                 **kwargs)

    async def update_test_item(self, item_uuid: str, attributes: Optional[Union[List, Dict]] = None,
                               description: Optional[str] = None) -> Optional[str]:
        return await self.__client.update_test_item(item_uuid, attributes=attributes, description=description)

    def _add_current_item(self, item: str) -> None:
        """Add the last item from the self._items queue."""
        self._item_stack.put(item)

    def _remove_current_item(self) -> str:
        """Remove the last item from the self._items queue."""
        return self._item_stack.get()

    def current_item(self) -> str:
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
                  attachment: Optional[Dict] = None, item_id: Optional[str] = None) -> None:
        return

    def clone(self) -> 'AsyncRPClient':
        """Clone the client object, set current Item ID as cloned item ID.

        :returns: Cloned client object
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


class ScheduledRPClient(RPClient):
    __client: _AsyncRPClient
    _item_stack: _LifoQueue
    __loop: Optional[asyncio.AbstractEventLoop]
    __thread: Optional[threading.Thread]
    __task_list: List[asyncio.Task]
    self_loop: bool
    self_thread: bool
    launch_uuid: Optional[asyncio.Task]
    use_own_launch: bool
    step_reporter: StepReporter

    def __init__(self, endpoint: str, project: str, *, launch_uuid: Optional[asyncio.Task] = None,
                 client: Optional[_AsyncRPClient] = None, loop: Optional[asyncio.AbstractEventLoop] = None,
                 **kwargs: Any) -> None:
        set_current(self)
        self.step_reporter = StepReporter(self)
        self._item_stack = _LifoQueue()
        if client:
            self.__client = client
        else:
            self.__client = _AsyncRPClient(endpoint, project, **kwargs)
        if launch_uuid:
            self.launch_uuid = launch_uuid
            self.use_own_launch = False
        else:
            self.use_own_launch = True

        self.__task_list = []
        self.__thread = None
        if loop:
            self.__loop = loop
            self.self_loop = False
        else:
            self.__loop = asyncio.new_event_loop()
            self.self_loop = True

    def create_task(self, coro: Any) -> asyncio.Task:
        loop = self.__loop
        result = loop.create_task(coro)
        self.__task_list.append(result)
        if not self.__thread and self.self_loop:
            self.__thread = threading.Thread(target=loop.run_forever, name='RP-Async-Client',
                                             daemon=True)
            self.__thread.start()
        i = 0
        for i, task in enumerate(self.__task_list):
            if not task.done():
                break
        self.__task_list = self.__task_list[i:]
        return result

    def finish_tasks(self):
        sleep_time = sys.getswitchinterval()
        shutdown_start_time = time.time()
        for task in self.__task_list:
            task_start_time = time.time()
            while not task.done() and (time.time() - task_start_time < TASK_TIMEOUT) and (
                    time.time() - shutdown_start_time < SHUTDOWN_TIMEOUT):
                time.sleep(sleep_time)
            if time.time() - shutdown_start_time >= SHUTDOWN_TIMEOUT:
                break
        self.__task_list = []

    async def __empty_line(self):
        return ""

    def start_launch(self,
                     name: str,
                     start_time: str,
                     description: Optional[str] = None,
                     attributes: Optional[Union[List, Dict]] = None,
                     rerun: bool = False,
                     rerun_of: Optional[str] = None,
                     **kwargs) -> asyncio.Task:
        if not self.use_own_launch:
            return self.launch_uuid
        launch_uuid_coro = self.__client.start_launch(name, start_time, description=description,
                                                      attributes=attributes, rerun=rerun, rerun_of=rerun_of,
                                                      **kwargs)
        self.launch_uuid = self.create_task(launch_uuid_coro)
        return self.launch_uuid

    def start_test_item(self,
                        name: str,
                        start_time: str,
                        item_type: str,
                        *,
                        description: Optional[str] = None,
                        attributes: Optional[List[Dict]] = None,
                        parameters: Optional[Dict] = None,
                        parent_item_id: Optional[asyncio.Task] = None,
                        has_stats: bool = True,
                        code_ref: Optional[str] = None,
                        retry: bool = False,
                        test_case_id: Optional[str] = None,
                        **kwargs: Any) -> asyncio.Task:

        item_id_coro = self.__client.start_test_item(self.launch_uuid, name, start_time, item_type,
                                                     description=description, attributes=attributes,
                                                     parameters=parameters, parent_item_id=parent_item_id,
                                                     has_stats=has_stats, code_ref=code_ref, retry=retry,
                                                     test_case_id=test_case_id, **kwargs)
        item_id_task = self.create_task(item_id_coro)
        self._add_current_item(item_id_task)
        return item_id_task

    def finish_test_item(self,
                         item_id: asyncio.Task,
                         end_time: str,
                         *,
                         status: str = None,
                         issue: Optional[Issue] = None,
                         attributes: Optional[Union[List, Dict]] = None,
                         description: str = None,
                         retry: bool = False,
                         **kwargs: Any) -> asyncio.Task:
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
                      **kwargs: Any) -> asyncio.Task:
        if self.use_own_launch:
            result_coro = self.__client.finish_launch(self.launch_uuid, end_time, status=status,
                                                      attributes=attributes, **kwargs)
        else:
            result_coro = self.create_task(self.__empty_line())

        result_task = self.create_task(result_coro)
        self.finish_tasks()
        return result_task

    def update_test_item(self,
                         item_uuid: asyncio.Task,
                         attributes: Optional[Union[List, Dict]] = None,
                         description: Optional[str] = None) -> asyncio.Task:
        result_coro = self.__client.update_test_item(item_uuid, attributes=attributes,
                                                     description=description)
        result_task = self.create_task(result_coro)
        return result_task

    def _add_current_item(self, item: asyncio.Task) -> None:
        """Add the last item from the self._items queue."""
        self._item_stack.put(item)

    def _remove_current_item(self) -> asyncio.Task:
        """Remove the last item from the self._items queue."""
        return self._item_stack.get()

    async def __empty_dict(self):
        return {}

    async def __none_value(self):
        return

    def current_item(self) -> asyncio.Task:
        """Retrieve the last item reported by the client."""
        return self._item_stack.last()

    def get_launch_info(self) -> asyncio.Task:
        if not self.launch_uuid:
            return self.create_task(self.__empty_dict())
        result_coro = self.__client.get_launch_info(self.launch_uuid)
        result_task = self.create_task(result_coro)
        return result_task

    def get_item_id_by_uuid(self, item_uuid_future: asyncio.Task) -> asyncio.Task:
        result_coro = self.__client.get_item_id_by_uuid(item_uuid_future)
        result_task = self.create_task(result_coro)
        return result_task

    def get_launch_ui_id(self) -> asyncio.Task:
        if not self.launch_uuid:
            return self.create_task(self.__none_value())
        result_coro = self.__client.get_launch_ui_id(self.launch_uuid)
        result_task = self.create_task(result_coro)
        return result_task

    def get_launch_ui_url(self) -> asyncio.Task:
        if not self.launch_uuid:
            return self.create_task(self.__none_value())
        result_coro = self.__client.get_launch_ui_url(self.launch_uuid)
        result_task = self.create_task(result_coro)
        return result_task

    def get_project_settings(self) -> asyncio.Task:
        result_coro = self.__client.get_project_settings()
        result_task = self.create_task(result_coro)
        return result_task

    def log(self, time: str, message: str, level: Optional[Union[int, str]] = None,
            attachment: Optional[Dict] = None, item_id: Optional[str] = None) -> None:
        # TODO: implement logging
        return None

    def clone(self) -> 'ScheduledRPClient':
        """Clone the client object, set current Item ID as cloned item ID.

        :returns: Cloned client object
        :rtype: ScheduledRPClient
        """
        cloned_client = self.__client.clone()
        # noinspection PyTypeChecker
        cloned = ScheduledRPClient(
            endpoint=None,
            project=None,
            launch_uuid=self.launch_uuid,
            client=cloned_client,
            loop=self.__loop
        )
        current_item = self.current_item()
        if current_item:
            cloned._add_current_item(current_item)
        return cloned
