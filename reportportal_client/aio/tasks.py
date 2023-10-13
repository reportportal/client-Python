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
from abc import abstractmethod
from asyncio import Future
from typing import TypeVar, Generic, Union, Generator, Awaitable, Optional

# noinspection PyProtectedMember
from reportportal_client._internal.static.abstract import AbstractBaseClass

_T = TypeVar('_T')


class BlockingOperationError(RuntimeError):
    """An issue with task blocking execution."""


class Task(Generic[_T], asyncio.Task, metaclass=AbstractBaseClass):
    """Base class for ReportPortal client tasks.

    Its main function to provide interface of 'blocking_result' method which is used to block current Thread
    until the result computation.
    """

    __metaclass__ = AbstractBaseClass

    name: Optional[str]

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
        self.name = name
        if sys.version_info < (3, 8):
            super().__init__(coro, loop=loop)
        else:
            super().__init__(coro, loop=loop, name=name)

    @abstractmethod
    def blocking_result(self) -> _T:
        """Block current Thread and wait for the task result.

        :return: execution result or raise an error
        """
        raise NotImplementedError('"blocking_result" method is not implemented!')

    def __repr__(self) -> str:
        """Return the result's repr function output if the Task is completed, or the Task's if not.

        :return: canonical string representation of the result or the current Task
        """
        if self.done():
            return repr(self.result())
        return super().__repr__()

    def __str__(self):
        """Return the result's str function output if the Task is completed, or the Task's if not.

        :return: string object from the result or from the current Task
        """
        if self.done():
            return str(self.result())
        return super().__str__()
