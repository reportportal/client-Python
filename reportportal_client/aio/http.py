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
from typing import Coroutine

from aenum import Enum
from aiohttp import ClientSession, ClientResponse, ServerConnectionError, \
    ClientResponseError

DEFAULT_RETRY_NUMBER: int = 5
DEFAULT_RETRY_DELAY: float = 0.005
THROTTLING_STATUSES: set = {425, 429}
RETRY_STATUSES: set = {408, 500, 502, 503, 507}.union(THROTTLING_STATUSES)


class RetryClass(int, Enum):
    SERVER_ERROR = 1
    CONNECTION_ERROR = 2
    THROTTLING = 3


class RetryingClientSession(ClientSession):
    __retry_number: int
    __retry_delay: float

    def __init__(
            self,
            *args,
            max_retry_number: int = DEFAULT_RETRY_NUMBER,
            base_retry_delay: float = DEFAULT_RETRY_DELAY,
            **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.__retry_number = max_retry_number
        self.__retry_delay = base_retry_delay

    async def __nothing(self):
        pass

    def __sleep(self, retry_num: int, retry_factor: int) -> Coroutine:
        if retry_num > 0:  # don't wait at the first retry attempt
            delay = (((retry_factor * self.__retry_delay) * 1000) ** retry_num) / 1000
            return asyncio.sleep(delay)
        else:
            return self.__nothing()

    async def _request(
            self,
            *args,
            **kwargs
    ) -> ClientResponse:
        result = None
        exceptions = []
        for i in range(self.__retry_number + 1):  # add one for the first attempt, which is not a retry
            retry_factor = None
            try:
                result = await super()._request(*args, **kwargs)
            except Exception as exc:
                exceptions.append(exc)
                if isinstance(exc, ServerConnectionError) or isinstance(exc, ClientResponseError):
                    retry_factor = RetryClass.CONNECTION_ERROR

                if not retry_factor:
                    raise exc

            if result:
                if result.ok or result.status not in RETRY_STATUSES:
                    return result

                if result.status in THROTTLING_STATUSES:
                    retry_factor = RetryClass.THROTTLING
                else:
                    retry_factor = RetryClass.SERVER_ERROR

            if i + 1 < self.__retry_number:
                # don't wait at the last attempt
                await self.__sleep(i, retry_factor)

        if exceptions:
            if len(exceptions) > 1:
                if sys.version_info > (3, 10):
                    # noinspection PyCompatibility
                    raise ExceptionGroup('During retry attempts the following exceptions happened',
                                         exceptions)
                else:
                    raise exceptions[-1]
            else:
                raise exceptions[0]
        return result
