#  Copyright 2026 EPAM Systems
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      https://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

"""This module contains auxiliary functions for async code."""

import asyncio
from typing import Coroutine, Optional, TypeVar, Union

from reportportal_client.aio.tasks import Task

_T = TypeVar("_T")


async def await_if_necessary(obj: Union[_T, Task[_T], Coroutine[_T, None, None]]) -> Optional[_T]:
    """Await Coroutine, Feature or coroutine Function if given argument is one of them, or return immediately.

    :param obj: value, Coroutine, Feature or coroutine Function
    :return: result which was returned by Coroutine, Feature or coroutine Function
    """
    if obj:
        if asyncio.isfuture(obj) or asyncio.iscoroutine(obj):
            return await obj
        elif asyncio.iscoroutinefunction(obj):
            return await obj()
    return obj
