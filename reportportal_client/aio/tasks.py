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
import sys
import threading
import time
import warnings
from abc import abstractmethod
from asyncio import Future
from typing import TypeVar, Generic, Union, Generator, Awaitable, Optional, Coroutine, Any

from reportportal_client.static.abstract import AbstractBaseClass

_T = TypeVar('_T')


class BlockingOperationError(RuntimeError):
    """An issue with task blocking execution."""


class Task(Generic[_T], asyncio.Task, metaclass=AbstractBaseClass):
    __metaclass__ = AbstractBaseClass

    def __init__(
            self,
            coro: Union[Generator[Future[object], None, _T], Awaitable[_T]],
            *,
            loop: asyncio.AbstractEventLoop,
            name: Optional[str] = None
    ) -> None:
        super().__init__(coro, loop=loop, name=name)

    @abstractmethod
    def blocking_result(self) -> _T:
        raise NotImplementedError('"blocking_result" method is not implemented!')


class BatchedTask(Generic[_T], Task[_T]):
    __loop: asyncio.AbstractEventLoop
    __thread: threading.Thread

    def __init__(
            self,
            coro: Union[Generator[Future[object], None, _T], Awaitable[_T]],
            *,
            loop: asyncio.AbstractEventLoop,
            name: Optional[str] = None,
            thread: threading.Thread
    ) -> None:
        super().__init__(coro, loop=loop, name=name)
        self.__loop = loop
        self.__thread = thread

    def blocking_result(self) -> _T:
        if self.done():
            return self.result()
        if self.__thread is not threading.current_thread():
            warnings.warn("The method was called from different thread which was used to create the"
                          "task, unexpected behavior is possible during the execution.", RuntimeWarning,
                          stacklevel=3)
        return self.__loop.run_until_complete(self)


class ThreadedTask(Generic[_T], Task[_T]):
    __loop: asyncio.AbstractEventLoop
    __wait_timeout: float

    def __init__(
            self,
            coro: Union[Generator[Future[object], None, _T], Awaitable[_T]],
            wait_timeout: float,
            *,
            loop: asyncio.AbstractEventLoop,
            name: Optional[str] = None
    ) -> None:
        super().__init__(coro, loop=loop, name=name)
        self.__loop = loop
        self.__wait_timeout = wait_timeout

    def blocking_result(self) -> _T:
        if self.done():
            return self.result()
        if not self.__loop.is_running() or self.__loop.is_closed():
            raise BlockingOperationError('Running loop is not alive')
        start_time = time.time()
        slee_time = sys.getswitchinterval()
        while not self.done() or time.time() - start_time < self.__wait_timeout:
            time.sleep(slee_time)
        if not self.done():
            raise BlockingOperationError('Timed out waiting for the task execution')
        return self.result()


class BatchedTaskFactory:
    __loop: asyncio.AbstractEventLoop
    __thread: threading.Thread

    def __init__(self, loop: asyncio.AbstractEventLoop, thread: threading.Thread):
        self.__loop = loop
        self.__thread = thread

    def __call__(
            self,
            loop: asyncio.AbstractEventLoop,
            factory: Union[Coroutine[Any, Any, _T], Generator[Any, None, _T]]
    ) -> Task[_T]:
        return BatchedTask(factory, loop=self.__loop, thread=self.__thread)


class ThreadedTaskFactory:
    __loop: asyncio.AbstractEventLoop
    __wait_timeout: float

    def __init__(self, loop: asyncio.AbstractEventLoop, wait_timeout: float):
        self.__loop = loop
        self.__wait_timeout = wait_timeout

    def __call__(
            self,
            loop: asyncio.AbstractEventLoop,
            factory: Union[Coroutine[Any, Any, _T], Generator[Any, None, _T]]
    ) -> Task[_T]:
        return ThreadedTask(factory, self.__wait_timeout, loop=self.__loop)
