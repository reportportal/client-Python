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
#
#  https://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License

"""This module designed to help with asynchronous HTTP request/response handling."""

import asyncio
import sys
from types import TracebackType
from typing import Any, Callable, Coroutine, Optional, Type, Union

from aenum import Enum
from aiohttp import ClientResponse, ClientResponseError
from aiohttp import ClientSession as AioHttpClientSession
from aiohttp import ServerConnectionError

from reportportal_client._internal.services.auth import AuthAsync

DEFAULT_RETRY_NUMBER: int = 5
DEFAULT_RETRY_DELAY: float = 0.005
THROTTLING_STATUSES: set = {425, 429}
RETRY_STATUSES: set = {408, 500, 502, 503, 507}.union(THROTTLING_STATUSES)
AUTH_PROBLEM_STATUSES: set = {401, 403}


class RetryClass(int, Enum):
    """Enum contains error types and their retry delay multiply factor as values."""

    SERVER_ERROR = 1
    CONNECTION_ERROR = 2
    THROTTLING = 3


class RetryingClientSession:
    """Class uses aiohttp.ClientSession.request method and adds request retry logic."""

    _client: AioHttpClientSession
    __retry_number: int
    __retry_delay: float

    def __init__(
        self,
        *args,
        max_retry_number: int = DEFAULT_RETRY_NUMBER,
        base_retry_delay: float = DEFAULT_RETRY_DELAY,
        **kwargs,
    ):
        """Initialize an instance of the session with arguments.

        To obtain the full list of arguments please see aiohttp.ClientSession.__init__() method. This class
        just bypass everything to the base method, except two local arguments 'max_retry_number' and
        'base_retry_delay'.

        :param max_retry_number: the maximum number of the request retries if it was unsuccessful
        :param base_retry_delay: base value for retry delay, determine how much time the class will wait after
                                 an error. Real value highly depends on Retry Class and Retry attempt number,
                                 since retries are performed in exponential delay manner
        """
        self._client = AioHttpClientSession(*args, **kwargs)
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

    async def __request(self, method: Callable, url, **kwargs: Any) -> ClientResponse:
        """Make a request and retry if necessary.

        The method retries requests depending on error class and retry number. For no-retry errors, such as
        400 Bad Request it just returns result, for cases where it's reasonable to retry it does it in
        exponential manner.
        """
        result = None
        exceptions = []

        for i in range(self.__retry_number + 1):  # add one for the first attempt, which is not a retry
            retry_factor = None
            if result is not None:
                # Release previous result to return connection to pool
                await result.release()
            try:
                result = await method(url, **kwargs)
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
                    raise ExceptionGroup(  # noqa: F821
                        "During retry attempts the following exceptions happened", exceptions
                    )
                else:
                    raise exceptions[-1]
            else:
                raise exceptions[0]
        return result

    def get(self, url: str, *, allow_redirects: bool = True, **kwargs: Any) -> Coroutine[Any, Any, ClientResponse]:
        """Perform HTTP GET request."""
        return self.__request(self._client.get, url, allow_redirects=allow_redirects, **kwargs)

    def post(self, url: str, *, data: Any = None, **kwargs: Any) -> Coroutine[Any, Any, ClientResponse]:
        """Perform HTTP POST request."""
        return self.__request(self._client.post, url, data=data, **kwargs)

    def put(self, url: str, *, data: Any = None, **kwargs: Any) -> Coroutine[Any, Any, ClientResponse]:
        """Perform HTTP PUT request."""
        return self.__request(self._client.put, url, data=data, **kwargs)

    def close(self) -> Coroutine:
        """Gracefully close internal aiohttp.ClientSession class instance."""
        return self._client.close()

    async def __aenter__(self) -> "RetryingClientSession":
        """Auxiliary method which controls what `async with` construction does on block enter."""
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        """Auxiliary method which controls what `async with` construction does on block exit."""
        await self.close()


class ClientSession:
    """Class wraps aiohttp.ClientSession or RetryingClientSession and adds authentication support."""

    _client: Union[AioHttpClientSession, RetryingClientSession]
    __auth: Optional[AuthAsync]

    def __init__(
        self,
        wrapped: Union[AioHttpClientSession, RetryingClientSession],
        auth: Optional[AuthAsync] = None,
    ):
        """Initialize an instance of the session with arguments.

        :param wrapped: aiohttp.ClientSession or RetryingClientSession instance to wrap
        :param auth:    authentication instance to use for requests
        """
        self._client = wrapped
        self.__auth = auth

    async def __request(self, method: Callable, url: str, **kwargs: Any) -> ClientResponse:
        """Make a request with authentication support.

        The method adds Authorization header if auth is configured and handles auth refresh
        on 401/403 responses.
        """
        # Clone kwargs and add Authorization header if auth is configured
        request_kwargs = kwargs.copy()
        if self.__auth:
            auth_header = await self.__auth.get()
            if auth_header:
                if "headers" not in request_kwargs:
                    request_kwargs["headers"] = {}
                else:
                    request_kwargs["headers"] = request_kwargs["headers"].copy()
                request_kwargs["headers"]["Authorization"] = auth_header

        result = await method(url, **request_kwargs)

        # Check for authentication errors
        if result.status in AUTH_PROBLEM_STATUSES and self.__auth:
            refreshed_header = await self.__auth.refresh()
            if refreshed_header:
                # Release previous result to return connection to pool
                await result.release()
                # Retry with new auth header
                request_kwargs["headers"] = request_kwargs.get("headers", {}).copy()
                request_kwargs["headers"]["Authorization"] = refreshed_header
                result = await method(url, **request_kwargs)

        return result

    def get(self, url: str, *, allow_redirects: bool = True, **kwargs: Any) -> Coroutine[Any, Any, ClientResponse]:
        """Perform HTTP GET request."""
        return self.__request(self._client.get, url, allow_redirects=allow_redirects, **kwargs)

    def post(self, url: str, *, data: Any = None, **kwargs: Any) -> Coroutine[Any, Any, ClientResponse]:
        """Perform HTTP POST request."""
        return self.__request(self._client.post, url, data=data, **kwargs)

    def put(self, url: str, *, data: Any = None, **kwargs: Any) -> Coroutine[Any, Any, ClientResponse]:
        """Perform HTTP PUT request."""
        return self.__request(self._client.put, url, data=data, **kwargs)

    def close(self) -> Coroutine:
        """Gracefully close internal session instance."""
        return self._client.close()

    async def __aenter__(self) -> "ClientSession":
        """Auxiliary method which controls what `async with` construction does on block enter."""
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        """Auxiliary method which controls what `async with` construction does on block exit."""
        await self.close()
