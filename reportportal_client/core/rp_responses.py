#  Copyright (c) 2022 EPAM Systems
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

"""This module contains models for the ReportPortal response objects.

Detailed information about responses wrapped up in that module
can be found by the following link:
https://github.com/reportportal/documentation/blob/master/src/md/src/DevGuides/reporting.md
"""

import logging
from typing import Any, Generator, Mapping, Optional, Tuple, Union

from aiohttp import ClientError, ClientResponse
from requests import Response

# noinspection PyProtectedMember
from reportportal_client._internal.static.defines import NOT_SET

logger = logging.getLogger(__name__)


def _iter_json_messages(json: Any) -> Generator[str, None, None]:
    if not isinstance(json, Mapping):
        return
    data = json.get("responses", [json])
    for chunk in data:
        if "message" not in chunk:
            continue
        message = chunk["message"]
        if message:
            yield message


def _get_json_decode_error_message(response: Union[Response, ClientResponse]) -> str:
    status = getattr(response, "status", getattr(response, "status_code", None))
    ok = getattr(response, "ok", None)
    return (
        f'Unable to decode JSON response, got {"passed" if ok else "failed"} '
        f'response with code "{status}" please check your endpoint configuration or API key'
    )


def _get_field(name: str, json: Optional[Any]) -> Optional[str]:
    if json is None:
        return None
    if name not in json:
        logger.warning(f"Unable to get '{name}' from json: {str(json)}")
        return None
    result_id = json[name]
    if result_id is None:
        logger.warning(f"Unable to get '{name}' from json: {str(json)}")
    return result_id


class RPResponse:
    """Class representing ReportPortal API response."""

    _resp: Response
    __json: Any

    def __init__(self, data: Response) -> None:
        """Initialize an instance with attributes.

        :param data: requests.Response object
        """
        self._resp = data
        self.__json = NOT_SET

    @property
    def id(self) -> Optional[str]:
        """Get value of the 'id' key in the response.

        :return: ID as string or NOT_FOUND, or None if the response is not JSON
        """
        json = self.json
        return _get_field("id", json)

    @property
    def is_success(self) -> bool:
        """Check if response to API has been successful.

        :return: is response successful
        """
        return self._resp.ok

    @property
    def json(self) -> Any:
        """Get the response in Dictionary or List.

        :return: JSON represented as Dictionary or List, or None if the response is not JSON
        """
        if self.__json is NOT_SET:
            try:
                self.__json = self._resp.json()
            except (ValueError, TypeError) as exc:
                logger.error(_get_json_decode_error_message(self._resp), exc_info=exc)
                self.__json = None
        return self.__json

    @property
    def message(self) -> Optional[str]:
        """Get value of the 'message' key in the response.

        :return: message as string or NOT_FOUND, or None if the response is not JSON
        """
        return _get_field("message", self.json)

    @property
    def messages(self) -> Optional[Tuple[str, ...]]:
        """Get list of messages received in the response.

        :return: a variable size tuple of strings or NOT_FOUND, or None if the response is not JSON
        """
        if self.json is None:
            return None
        return tuple(_iter_json_messages(self.json))


class AsyncRPResponse:
    """Class representing ReportPortal API asynchronous response."""

    _resp: ClientResponse
    __json: Any

    def __init__(self, data: ClientResponse) -> None:
        """Initialize an instance with attributes.

        :param data: aiohttp.ClientResponse object
        """
        self._resp = data
        self.__json = NOT_SET

    @property
    async def id(self) -> Optional[str]:
        """Get value of the 'id' key in the response.

        :return: ID as string or NOT_FOUND, or None if the response is not JSON
        """
        json = await self.json
        return _get_field("id", json)

    @property
    def is_success(self) -> bool:
        """Check if response to API has been successful.

        :return: is response successful
        """
        return self._resp.ok

    @property
    async def json(self) -> Any:
        """Get the response in Dictionary or List.

        :return: JSON represented as Dictionary or List, or None if the response is not JSON
        """
        if self.__json is NOT_SET:
            try:
                self.__json = await self._resp.json()
            except (ValueError, TypeError, ClientError) as exc:
                logger.error(_get_json_decode_error_message(self._resp), exc_info=exc)
                self.__json = None
        return self.__json

    @property
    async def message(self) -> Optional[str]:
        """Get value of the 'message' key in the response.

        :return: message as string or NOT_FOUND, or None if the response is not JSON
        """
        return _get_field("message", await self.json)

    @property
    async def messages(self) -> Optional[Tuple[str, ...]]:
        """Get list of messages received in the response.

        :return: a variable size tuple of strings or NOT_FOUND, or None if the response is not JSON
        """
        json = await self.json
        if json is None:
            return None
        return tuple(_iter_json_messages(json))
