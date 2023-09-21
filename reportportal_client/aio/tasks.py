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
import time
from abc import abstractmethod
from asyncio import Future
from typing import TypeVar, Generic, Union, Generator, Awaitable, Optional, Coroutine, Any, List

from reportportal_client.static.abstract import AbstractBaseClass

_T = TypeVar('_T')
DEFAULT_TASK_TRIGGER_NUM: int = 10
DEFAULT_TASK_TRIGGER_INTERVAL: float = 1.0


class BlockingOperationError(RuntimeError):
    """An issue with task blocking execution."""


class Task(Generic[_T], asyncio.Task, metaclass=AbstractBaseClass):
    __metaclass__ = AbstractBaseClass

    def __init__(
            self,
            coro: Union[Generator[Future[Any], None, _T], Awaitable[_T]],
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

    def __init__(
            self,
            coro: Union[Generator[Future[Any], None, _T], Awaitable[_T]],
            *,
            loop: asyncio.AbstractEventLoop,
            name: Optional[str] = None
    ) -> None:
        super().__init__(coro, loop=loop, name=name)
        self.__loop = loop

    def blocking_result(self) -> _T:
        if self.done():
            return self.result()
        return self.__loop.run_until_complete(self)

    def __repr__(self) -> str:
        if self.done():
            return repr(self.result())
        return super().__repr__()

    def __str__(self):
        if self.done():
            return str(self.result())
        return super().__str__()


class ThreadedTask(Generic[_T], Task[_T]):
    __loop: asyncio.AbstractEventLoop
    __wait_timeout: float

    def __init__(
            self,
            coro: Union[Generator[Future[Any], None, _T], Awaitable[_T]],
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
        sleep_time = sys.getswitchinterval()
        while not self.done() and time.time() - start_time < self.__wait_timeout:
            time.sleep(sleep_time)
        if not self.done():
            raise BlockingOperationError('Timed out waiting for the task execution')
        return self.result()

    def __repr__(self) -> str:
        if self.done():
            return repr(self.result())
        return super().__repr__()

    def __str__(self):
        if self.done():
            return str(self.result())
        return super().__str__()


class BatchedTaskFactory:
    __loop: asyncio.AbstractEventLoop

    def __init__(self, loop: asyncio.AbstractEventLoop):
        self.__loop = loop

    def __call__(
            self,
            loop: asyncio.AbstractEventLoop,
            factory: Union[Coroutine[Any, Any, _T], Generator[Any, None, _T]],
            **_
    ) -> Task[_T]:
        return BatchedTask(factory, loop=self.__loop)


class ThreadedTaskFactory:
    __loop: asyncio.AbstractEventLoop
    __wait_timeout: float

    def __init__(self, loop: asyncio.AbstractEventLoop, wait_timeout: float):
        self.__loop = loop
        self.__wait_timeout = wait_timeout

    def __call__(
            self,
            loop: asyncio.AbstractEventLoop,
            factory: Union[Coroutine[Any, Any, _T], Generator[Any, None, _T]],
            **_
    ) -> Task[_T]:
        return ThreadedTask(factory, self.__wait_timeout, loop=self.__loop)


class TriggerTaskList(Generic[_T]):
    __task_list: List[_T]
    __last_run_time: float
    __trigger_num: int
    __trigger_interval: float

    def __init__(self,
                 trigger_num: int = DEFAULT_TASK_TRIGGER_NUM,
                 trigger_interval: float = DEFAULT_TASK_TRIGGER_INTERVAL):
        self.__task_list = []
        self.__last_run_time = time.time()
        self.__trigger_num = trigger_num
        self.__trigger_interval = trigger_interval

    def __ready_to_run(self) -> bool:
        current_time = time.time()
        last_time = self.__last_run_time
        if len(self.__task_list) <= 0:
            return False
        if (len(self.__task_list) >= self.__trigger_num
                or current_time - last_time >= self.__trigger_interval):
            self.__last_run_time = current_time
            return True
        return False

    def append(self, value: _T) -> Optional[List[_T]]:
        self.__task_list.append(value)
        if self.__ready_to_run():
            tasks = self.__task_list
            self.__task_list = []
            return tasks

    def flush(self) -> Optional[List[_T]]:
        if len(self.__task_list) > 0:
            tasks = self.__task_list
            self.__task_list = []
            return tasks


class BackgroundTaskList(Generic[_T]):
    __task_list: List[_T]

    def __init__(self):
        self.__task_list = []

    def __remove_finished(self):
        i = -1
        for task in self.__task_list:
            if not task.done():
                break
            i += 1
        self.__task_list = self.__task_list[i + 1:]

    def append(self, value: _T) -> None:
        self.__remove_finished()
        self.__task_list.append(value)

    def flush(self) -> Optional[List[_T]]:
        self.__remove_finished()
        if len(self.__task_list) > 0:
            tasks = self.__task_list
            self.__task_list = []
            return tasks
