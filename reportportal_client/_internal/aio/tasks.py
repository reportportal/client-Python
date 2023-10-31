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

"""This module contains customized asynchronous Tasks and Task Factories for the ReportPortal client."""

import asyncio
import sys
import time
from asyncio import Future
from typing import Optional, List, TypeVar, Generic, Union, Generator, Awaitable, Coroutine, Any

from reportportal_client.aio.tasks import Task, BlockingOperationError

_T = TypeVar('_T')

DEFAULT_TASK_TRIGGER_NUM: int = 10
DEFAULT_TASK_TRIGGER_INTERVAL: float = 1.0


class BatchedTask(Generic[_T], Task[_T]):
    """Represents a Task which uses the current Thread to execute itself."""

    __loop: asyncio.AbstractEventLoop

    def __init__(
            self,
            coro: Union[Generator[Future, None, _T], Awaitable[_T]],
            *,
            loop: asyncio.AbstractEventLoop,
            name: Optional[str] = None
    ) -> None:
        """Initialize an instance of the Task.

        :param coro: Future, Coroutine or a Generator of these objects, which will be executed
        :param loop: Event Loop which will be used to execute the Task
        :param name: the name of the task
        """
        super().__init__(coro, loop=loop, name=name)
        self.__loop = loop

    def blocking_result(self) -> _T:
        """Use current Thread to execute the Task and return the result if not yet executed.

        :return: execution result or raise an error, or return immediately if already executed
        """
        if self.done():
            return self.result()
        return self.__loop.run_until_complete(self)


class ThreadedTask(Generic[_T], Task[_T]):
    """Represents a Task which runs is a separate Thread."""

    __loop: asyncio.AbstractEventLoop
    __wait_timeout: float

    def __init__(
            self,
            coro: Union[Generator[Future, None, _T], Awaitable[_T]],
            wait_timeout: float,
            *,
            loop: asyncio.AbstractEventLoop,
            name: Optional[str] = None
    ) -> None:
        """Initialize an instance of the Task.

        :param coro: Future, Coroutine or a Generator of these objects, which will be executed
        :param loop: Event Loop which will be used to execute the Task
        :param name: the name of the task
        """
        super().__init__(coro, loop=loop, name=name)
        self.__loop = loop
        self.__wait_timeout = wait_timeout

    def blocking_result(self) -> _T:
        """Pause current Thread until the Task completion and return the result if not yet executed.

        :return: execution result or raise an error, or return immediately if already executed
        """
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


class BatchedTaskFactory:
    """Factory protocol which creates Batched Tasks."""

    def __call__(
            self,
            loop: asyncio.AbstractEventLoop,
            factory: Union[Coroutine[Any, Any, _T], Generator[Any, None, _T]],
            **_
    ) -> Task[_T]:
        """Create Batched Task in appropriate Event Loop.

        :param loop:    Event Loop which will be used to execute the Task
        :param factory: Future, Coroutine or a Generator of these objects, which will be executed
        """
        return BatchedTask(factory, loop=loop)


class ThreadedTaskFactory:
    """Factory protocol which creates Threaded Tasks."""

    __wait_timeout: float

    def __init__(self, wait_timeout: float):
        """Initialize an instance of the Factory.

        :param wait_timeout: Task wait timeout in case of blocking result get
        """
        self.__wait_timeout = wait_timeout

    def __call__(
            self,
            loop: asyncio.AbstractEventLoop,
            factory: Union[Coroutine[Any, Any, _T], Generator[Any, None, _T]],
            **_
    ) -> Task[_T]:
        """Create Threaded Task in appropriate Event Loop.

        :param loop:    Event Loop which will be used to execute the Task
        :param factory: Future, Coroutine or a Generator of these objects, which will be executed
        """
        return ThreadedTask(factory, self.__wait_timeout, loop=loop)


class TriggerTaskBatcher(Generic[_T]):
    """Batching class which compile its batches by object number or by passed time."""

    __task_list: List[_T]
    __last_run_time: float
    __trigger_num: int
    __trigger_interval: float

    def __init__(self,
                 trigger_num: int = DEFAULT_TASK_TRIGGER_NUM,
                 trigger_interval: float = DEFAULT_TASK_TRIGGER_INTERVAL) -> None:
        """Initialize an instance of the Batcher.

        :param trigger_num: object number threshold which triggers batch return and reset
        :param trigger_interval: amount of time after which return and reset batch
        """
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
        """Add an object to internal batch and return the batch if it's triggered.

        :param   value: an object to add to the batch
        :return: a batch or None
        """
        self.__task_list.append(value)
        if self.__ready_to_run():
            tasks = self.__task_list
            self.__task_list = []
            return tasks

    def flush(self) -> Optional[List[_T]]:
        """Immediately return everything what's left in the internal batch.

        :return: a batch or None
        """
        if len(self.__task_list) > 0:
            tasks = self.__task_list
            self.__task_list = []
            return tasks


class BackgroundTaskList(Generic[_T]):
    """Task list class which collects Tasks into internal batch and removes when they complete."""

    __task_list: List[_T]

    def __init__(self):
        """Initialize an instance of the Batcher."""
        self.__task_list = []

    def __remove_finished(self):
        i = -1
        for task in self.__task_list:
            if not task.done():
                break
            i += 1
        self.__task_list = self.__task_list[i + 1:]

    def append(self, value: _T) -> None:
        """Add an object to internal batch.

        :param value: an object to add to the batch
        """
        self.__remove_finished()
        self.__task_list.append(value)

    def flush(self) -> Optional[List[_T]]:
        """Immediately return everything what's left unfinished in the internal batch.

        :return: a batch or None
        """
        self.__remove_finished()
        if len(self.__task_list) > 0:
            tasks = self.__task_list
            self.__task_list = []
            return tasks
