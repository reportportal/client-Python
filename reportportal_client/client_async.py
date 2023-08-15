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
from queue import LifoQueue
from typing import Union, Tuple, List, Dict, Any, Optional, TextIO

import aiohttp

from .core.rp_issues import Issue
from .logs.log_manager import LogManager, MAX_LOG_BATCH_PAYLOAD_SIZE
from .static.defines import NOT_FOUND
from .steps import StepReporter

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


class _LifoQueue(LifoQueue):
    def last(self):
        with self.mutex:
            if self._qsize():
                return self.queue[-1]


class _RPClient:
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
    session: aiohttp.ClientSession = ...
    step_reporter: StepReporter = ...
    mode: str = ...
    launch_uuid_print: Optional[bool] = ...
    print_output: Optional[TextIO] = ...
    _skip_analytics: str = ...
    _item_stack: _LifoQueue = ...

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
        self._item_stack = _LifoQueue()

    async def finish_launch(self,
                            end_time: str,
                            status: str = None,
                            attributes: Optional[Union[List, Dict]] = None,
                            **kwargs: Any) -> Optional[str]:
        pass

    async def finish_test_item(self,
                               item_id: Union[asyncio.Future, str],
                               end_time: str,
                               *,
                               status: str = None,
                               issue: Optional[Issue] = None,
                               attributes: Optional[Union[List, Dict]] = None,
                               description: str = None,
                               retry: bool = False,
                               **kwargs: Any) -> Optional[str]:
        pass

    async def get_item_id_by_uuid(self, uuid: Union[asyncio.Future, str]) -> Optional[str]:
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
                  item_id: Optional[Union[asyncio.Future, str]] = None) -> None:
        pass

    async def start_launch(self,
                           name: str,
                           start_time: str,
                           description: Optional[str] = None,
                           attributes: Optional[Union[List, Dict]] = None,
                           rerun: bool = False,
                           rerun_of: Optional[str] = None,
                           **kwargs) -> Optional[str]:
        pass

    async def start_test_item(self,
                              name: str,
                              start_time: str,
                              item_type: str,
                              *,
                              description: Optional[str] = None,
                              attributes: Optional[List[Dict]] = None,
                              parameters: Optional[Dict] = None,
                              parent_item_id: Optional[Union[asyncio.Future, str]] = None,
                              has_stats: bool = True,
                              code_ref: Optional[str] = None,
                              retry: bool = False,
                              test_case_id: Optional[str] = None,
                              **_: Any) -> Optional[str]:
        pass

    async def update_test_item(self, item_uuid: Union[asyncio.Future, str],
                               attributes: Optional[Union[List, Dict]] = None,
                               description: Optional[str] = None) -> Optional[str]:
        pass

    def _add_current_item(self, item: Union[asyncio.Future, str]) -> None:
        """Add the last item from the self._items queue."""
        self._item_stack.put(item)

    def _remove_current_item(self) -> None:
        """Remove the last item from the self._items queue."""
        return self._item_stack.get()

    def current_item(self) -> Union[asyncio.Future, str]:
        """Retrieve the last item reported by the client."""
        return self._item_stack.last()

    def clone(self) -> '_RPClient':
        """Clone the client object, set current Item ID as cloned item ID.

        :returns: Cloned client object
        :rtype: _RPClient
        """
        cloned = _RPClient(
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


class RPClientAsync(_RPClient):

    async def start_test_item(self,
                              name: str,
                              start_time: str,
                              item_type: str,
                              *,
                              description: Optional[str] = None,
                              attributes: Optional[List[Dict]] = None,
                              parameters: Optional[Dict] = None,
                              parent_item_id: Optional[Union[asyncio.Future, str]] = None,
                              has_stats: bool = True,
                              code_ref: Optional[str] = None,
                              retry: bool = False,
                              test_case_id: Optional[str] = None,
                              **_: Any) -> Optional[str]:
        item_id = await super().start_test_item(name, start_time, item_type, description=description,
                                                attributes=attributes, parameters=parameters,
                                                parent_item_id=parent_item_id, has_stats=has_stats,
                                                code_ref=code_ref, retry=retry, test_case_id=test_case_id)
        if item_id and item_id is not NOT_FOUND:
            super()._add_current_item(item_id)
        return item_id

    async def finish_test_item(self,
                               item_id: Union[asyncio.Future, str],
                               end_time: str,
                               *,
                               status: str = None,
                               issue: Optional[Issue] = None,
                               attributes: Optional[Union[List, Dict]] = None,
                               description: str = None,
                               retry: bool = False,
                               **kwargs: Any) -> Optional[str]:
        result = await super().finish_test_item(item_id, end_time, status=status, issue=issue,
                                                attributes=attributes, description=description, retry=retry)
        super()._remove_current_item()
        return result


class RPClientSync:

    client: _RPClient

    def __init__(self, client: _RPClient):
        self.client = client

