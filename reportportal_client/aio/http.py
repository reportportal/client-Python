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

import aiohttp
from aenum import auto, Enum
from aiohttp import ClientResponse
from sympy import fibonacci

DEFAULT_RETRY_NUMBER: int = 5
DEFAULT_RETRY_DELAY: int = 10


class RetryClass(Enum):
    CONNECTION_ERROR = auto()
    SERVER_ERROR = auto()
    BAD_REQUEST = auto()
    THROTTLING = auto()


RETRY_FACTOR = {
    RetryClass.CONNECTION_ERROR: 5,
    RetryClass.SERVER_ERROR: 1,
    RetryClass.BAD_REQUEST: 0,
    RetryClass.THROTTLING: 10
}


class RetryingClientSession(aiohttp.ClientSession):
    __retry_number: int
    __retry_delay: int

    def __init__(
            self,
            *args,
            retry_number: int = DEFAULT_RETRY_NUMBER,
            retry_delay: int = DEFAULT_RETRY_DELAY,
            **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.__retry_number = retry_number
        self.__retry_delay = retry_delay

    async def _request(
            self,
            *args,
            **kwargs
    ) -> ClientResponse:
        fibonacci(5)
        return await super()._request(*args, **kwargs)
