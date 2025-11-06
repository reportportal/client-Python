#  Copyright 2025 EPAM Systems
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
#  limitations under the License

"""This module designed to help with synchronous HTTP request/response handling."""

from types import TracebackType
from typing import Any, Callable, Optional, Type, Union

from requests import Response, Session
from requests.adapters import BaseAdapter

from reportportal_client._internal.services.auth import Auth

AUTH_PROBLEM_STATUSES: set = {401, 403}


class ClientSession:
    """Class wraps requests.Session and adds authentication support."""

    _client: Session
    __auth: Optional[Auth]

    def __init__(
        self,
        auth: Optional[Auth] = None,
    ):
        """Initialize an instance of the session with arguments.

        :param auth: authentication instance to use for requests
        """
        self._client = Session()
        self.__auth = auth

    def __request(self, method: Callable, url: Union[str, bytes], **kwargs: Any) -> Response:
        """Make a request with authentication support.

        The method adds Authorization header if auth is configured and handles auth refresh
        on 401/403 responses.
        """
        # Clone kwargs and add Authorization header if auth is configured
        request_kwargs = kwargs.copy()
        if self.__auth:
            auth_header = self.__auth.get()
            if auth_header:
                if "headers" not in request_kwargs:
                    request_kwargs["headers"] = {}
                else:
                    request_kwargs["headers"] = request_kwargs["headers"].copy()
                request_kwargs["headers"]["Authorization"] = auth_header

        result = method(url, **request_kwargs)

        # Check for authentication errors
        if result.status_code in AUTH_PROBLEM_STATUSES and self.__auth:
            refreshed_header = self.__auth.refresh()
            if refreshed_header:
                # Close previous result if it's retried to release resources
                result.close()
                # Retry with new auth header
                request_kwargs["headers"] = request_kwargs.get("headers", {}).copy()
                request_kwargs["headers"]["Authorization"] = refreshed_header
                result = method(url, **request_kwargs)

        return result

    def get(self, url: Union[str, bytes], **kwargs: Any) -> Response:
        """Perform HTTP GET request."""
        return self.__request(self._client.get, url, **kwargs)

    def post(self, url: Union[str, bytes], **kwargs: Any) -> Response:
        """Perform HTTP POST request."""
        return self.__request(self._client.post, url, **kwargs)

    def put(self, url: Union[str, bytes], **kwargs: Any) -> Response:
        """Perform HTTP PUT request."""
        return self.__request(self._client.put, url, **kwargs)

    def mount(self, prefix: str, adapter: BaseAdapter) -> None:
        """Mount an adapter to a specific URL prefix.

        :param prefix: URL prefix (e.g., 'http://', 'https://')
        :param adapter: Adapter instance to mount
        """
        self._client.mount(prefix, adapter)

    def close(self) -> None:
        """Gracefully close internal requests.Session class instance."""
        self._client.close()

    def __enter__(self) -> "ClientSession":
        """Auxiliary method which controls what `with` construction does on block enter."""
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        """Auxiliary method which controls what `with` construction does on block exit."""
        self.close()
