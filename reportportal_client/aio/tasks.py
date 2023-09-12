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
import threading
import warnings
from abc import abstractmethod
from asyncio import Future
from typing import TypeVar, Generic, Union, Generator, Awaitable, Optional, Coroutine, Any

from reportportal_client.static.abstract import AbstractBaseClass

_T = TypeVar('_T')


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
