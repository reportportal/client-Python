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
import warnings
from os import getenv
from queue import LifoQueue
from typing import Union, Tuple, List, Dict, Any, Optional, TextIO

import aiohttp

# noinspection PyProtectedMember
from reportportal_client._local import set_current
from reportportal_client.core.rp_issues import Issue
from reportportal_client.core.rp_requests import (LaunchStartRequest, AsyncHttpRequest, AsyncItemStartRequest,
                                                  AsyncItemFinishRequest, LaunchFinishRequest)
from reportportal_client.helpers import uri_join, verify_value_length, await_if_necessary, agent_name_version
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


class _LifoQueue(LifoQueue):
    def last(self):
        with self.mutex:
            if self._qsize():
                return self.queue[-1]


class _AsyncRPClient(metaclass=AbstractBaseClass):
    __metaclass__ = AbstractBaseClass

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
    step_reporter: StepReporter
    mode: str
    launch_uuid_print: Optional[bool]
    print_output: Optional[TextIO]
    _skip_analytics: str
    _item_stack: _LifoQueue
    __session: aiohttp.ClientSession

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
        self._item_stack = _LifoQueue()
        set_current(self)
        self.api_v1, self.api_v2 = 'v1', 'v2'
        self.endpoint = endpoint
        self.project = project
        self.base_url_v1 = uri_join(
            self.endpoint, 'api/{}'.format(self.api_v1), self.project)
        self.base_url_v2 = uri_join(
            self.endpoint, 'api/{}'.format(self.api_v2), self.project)
        self.is_skipped_an_issue = is_skipped_an_issue
        self.log_batch_size = log_batch_size
        self.log_batch_payload_size = log_batch_payload_size
        self.verify_ssl = verify_ssl
        self.retries = retries
        self.max_pool_size = max_pool_size
        self.http_timeout = http_timeout
        self.step_reporter = StepReporter(self)
        self._item_stack = _LifoQueue()
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

    @property
    def session(self) -> aiohttp.ClientSession:
        # TODO: add retry handler
        if self.__session:
            return self.__session

        ssl_config = self.verify_ssl
        if ssl_config and type(ssl_config) == str:
            ssl_context = ssl.create_default_context()
            ssl_context.load_cert_chain(ssl_config)
            ssl_config = ssl_context
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
        return uri_join(self.base_url_v2, 'item', item_id)

    async def __get_launch_url(self, launch_id_future: Union[str, asyncio.Task]) -> Optional[str]:
        launch_id = await await_if_necessary(launch_id_future)
        if launch_id is NOT_FOUND:
            logger.warning('Attempt to make request for non-existent launch.')
            return
        return uri_join(self.base_url_v2, 'launch', launch_id, 'finish')

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
        url = uri_join(self.base_url_v2, 'launch')
        request_payload = LaunchStartRequest(
            name=name,
            start_time=start_time,
            attributes=attributes,
            description=description,
            mode=self.mode,
            rerun=rerun,
            rerun_of=rerun_of or kwargs.get('rerunOf')
        ).payload

        launch_coro = AsyncHttpRequest(self.session.post,
                                       url=url,
                                       json=request_payload).make()

        stat_coro = None
        if not self._skip_analytics:
            stat_coro = async_send_event('start_launch', *agent_name_version(attributes))

        if stat_coro:
            response = (await asyncio.gather(launch_coro, stat_coro))[0]
        else:
            response = await launch_coro

        if not response:
            return

        launch_id = response.id
        logger.debug(f'start_launch - ID: %s', launch_id)
        if self.launch_uuid_print and self.print_output:
            print(f'Report Portal Launch UUID: {launch_id}', file=self.print_output)
        return launch_id

    async def start_test_item(self,
                              name: str,
                              start_time: str,
                              item_type: str,
                              launch_id: Union[str, asyncio.Task],
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
            url = uri_join(self.base_url_v2, 'item')
        request_payload = AsyncItemStartRequest(
            name,
            start_time,
            item_type,
            launch_id,
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
        item_id = response.id
        if item_id is NOT_FOUND:
            logger.warning('start_test_item - invalid response: %s',
                           str(response.json))
        return item_id

    async def finish_test_item(self,
                               item_id: Union[str, asyncio.Task],
                               end_time: str,
                               launch_id: Union[str, asyncio.Task],
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
            launch_id,
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
        logger.debug('finish_test_item - ID: %s', item_id)
        logger.debug('response message: %s', response.message)
        return response.message

    async def finish_launch(self,
                            launch_id: Union[str, asyncio.Task],
                            end_time: str,
                            *,
                            status: str = None,
                            attributes: Optional[Union[List, Dict]] = None,
                            **kwargs: Any) -> Optional[str]:
        url = self.__get_launch_url(launch_id)
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
        logger.debug('finish_launch - ID: %s', launch_id)
        logger.debug('response message: %s', response.message)
        return response.message

    async def get_item_id_by_uuid(self, uuid: Union[asyncio.Task, str]) -> Optional[str]:
        pass

    async def get_launch_info(self) -> Optional[Dict]:
        pass

    async def get_launch_ui_id(self) -> Optional[Dict]:
        pass

    async def get_launch_ui_url(self) -> Optional[str]:
        pass

    async def get_project_settings(self) -> Optional[Dict]:
        pass

    async def log(self, time: str, message: str, level: Optional[Union[int, str]] = None,
                  attachment: Optional[Dict] = None,
                  item_id: Optional[Union[asyncio.Task, str]] = None) -> None:
        pass

    async def update_test_item(self, item_uuid: Union[asyncio.Task, str],
                               attributes: Optional[Union[List, Dict]] = None,
                               description: Optional[str] = None) -> Optional[str]:
        pass

    def _add_current_item(self, item: Union[asyncio.Task, str]) -> None:
        """Add the last item from the self._items queue."""
        self._item_stack.put(item)

    def _remove_current_item(self) -> None:
        """Remove the last item from the self._items queue."""
        return self._item_stack.get()

    def current_item(self) -> Union[asyncio.Task, str]:
        """Retrieve the last item reported by the client."""
        return self._item_stack.last()

    @abstractmethod
    def clone(self) -> '_AsyncRPClient':
        """Abstract interface for cloning the client."""
        raise NotImplementedError('Clone interface is not implemented!')


class AsyncRPClient(_AsyncRPClient):
    launch_id: Optional[str]
    use_own_launch: bool

    def __init__(self, endpoint: str, project: str, *, launch_id: Optional[str] = None,
                 **kwargs: Any) -> None:
        super().__init__(endpoint, project, **kwargs)
        if launch_id:
            self.launch_id = launch_id
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
            return self.launch_id
        launch_id = await super().start_launch(name, start_time, description=description,
                                               attributes=attributes, rerun=rerun, rerun_of=rerun_of,
                                               **kwargs)
        self.launch_id = launch_id
        return launch_id

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
        item_id = await super().start_test_item(name, start_time, item_type, description=description,
                                                attributes=attributes, parameters=parameters,
                                                parent_item_id=parent_item_id, has_stats=has_stats,
                                                code_ref=code_ref, retry=retry, test_case_id=test_case_id,
                                                **kwargs)
        if item_id and item_id is not NOT_FOUND:
            logger.debug('start_test_item - ID: %s', item_id)
            super()._add_current_item(item_id)
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
        result = await super().finish_test_item(item_id, end_time, self.launch_id, status=status, issue=issue,
                                                attributes=attributes, description=description, retry=retry,
                                                **kwargs)
        super()._remove_current_item()
        return result

    async def finish_launch(self,
                            end_time: str,
                            status: str = None,
                            attributes: Optional[Union[List, Dict]] = None,
                            **kwargs: Any) -> Optional[str]:
        if not self.use_own_launch:
            return ""
        return await super().finish_launch(self.launch_id, end_time, status=status, attributes=attributes,
                                           **kwargs)

    def clone(self) -> 'AsyncRPClient':
        """Clone the client object, set current Item ID as cloned item ID.

        :returns: Cloned client object
        :rtype: AsyncRPClient
        """
        cloned = AsyncRPClient(
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
            cloned._add_current_item(current_item)
        return cloned


class SyncRPClient(_AsyncRPClient):
    loop: asyncio.AbstractEventLoop
    thread: threading.Thread
    self_loop: bool
    self_thread: bool
    launch_id: Optional[asyncio.Task]
    use_own_launch: bool

    def __init__(self, endpoint: str, project: str, *, launch_id: Optional[asyncio.Task] = None,
                 **kwargs: Any) -> None:
        super().__init__(endpoint, project, **kwargs)
        if launch_id:
            self.launch_id = launch_id
            self.use_own_launch = False
        else:
            self.use_own_launch = True

        if 'loop' in kwargs and kwargs['loop']:
            self.loop = kwargs['loop']
            self.self_loop = False
        else:
            self.loop = asyncio.new_event_loop()
            self.self_loop = True
        if 'thread' in kwargs and kwargs['thread']:
            self.thread = kwargs['thread']
            self.self_thread = False
        else:
            self.thread = threading.Thread(target=self.loop.run_forever(), name='RP-Async-Client',
                                           daemon=True)
            self.thread.start()
            self.self_thread = True

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
            return self.launch_id
        launch_id_coro = super().start_launch(name, start_time, description=description,
                                              attributes=attributes, rerun=rerun, rerun_of=rerun_of,
                                              **kwargs)
        launch_id_task = self.loop.create_task(launch_id_coro)
        self.launch_id = launch_id_task
        return launch_id_task

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

        item_id_coro = super().start_test_item(name, start_time, item_type, launch_id=self.launch_id,
                                               description=description,
                                               attributes=attributes, parameters=parameters,
                                               parent_item_id=parent_item_id, has_stats=has_stats,
                                               code_ref=code_ref, retry=retry, test_case_id=test_case_id,
                                               **kwargs)
        item_id_task = self.loop.create_task(item_id_coro)
        super()._add_current_item(item_id_task)
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
        result_coro = super().finish_test_item(item_id, end_time, self.launch_id, status=status, issue=issue,
                                               attributes=attributes, description=description, retry=retry,
                                               **kwargs)
        result_task = self.loop.create_task(result_coro)
        super()._remove_current_item()
        return result_task

    # TODO: implement loop task finish wait
    def finish_launch(self,
                      end_time: str,
                      status: str = None,
                      attributes: Optional[Union[List, Dict]] = None,
                      **kwargs: Any) -> asyncio.Task:
        if not self.use_own_launch:
            return self.loop.create_task(self.__empty_line())
        result_coro = super().finish_launch(self.launch_id, end_time, status=status, attributes=attributes,
                                            **kwargs)
        result_task = self.loop.create_task(result_coro)
        return result_task

    def clone(self) -> 'SyncRPClient':
        """Clone the client object, set current Item ID as cloned item ID.

        :returns: Cloned client object
        :rtype: SyncRPClient
        """
        cloned = SyncRPClient(
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
            mode=self.mode,
            loop=self.loop,
            thread=self.thread
        )
        current_item = self.current_item()
        if current_item:
            cloned._add_current_item(current_item)
        return cloned
