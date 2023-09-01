"""This module includes classes representing RP API requests.

Detailed information about requests wrapped up in that module
can be found by the following link:
https://github.com/reportportal/documentation/blob/master/src/md/src/DevGuides/reporting.md
"""

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

import asyncio
import json as json_converter
import logging
import ssl
from dataclasses import dataclass
from typing import Callable, Text, Optional, Union, List, Tuple, Any, TypeVar

import aiohttp

from reportportal_client import helpers
from reportportal_client.core.rp_file import RPFile
from reportportal_client.core.rp_issues import Issue
from reportportal_client.core.rp_responses import RPResponse
from reportportal_client.helpers import dict_to_payload
from reportportal_client.static.abstract import (
    AbstractBaseClass,
    abstractmethod
)
from reportportal_client.static.defines import (
    DEFAULT_PRIORITY,
    LOW_PRIORITY,
    RP_LOG_LEVELS, Priority
)

logger = logging.getLogger(__name__)
T = TypeVar("T")


async def await_if_necessary(obj: Optional[Any]) -> Any:
    if obj:
        if asyncio.isfuture(obj) or asyncio.iscoroutine(obj):
            return await obj
        elif asyncio.iscoroutinefunction(obj):
            return await obj()
    return obj


class HttpRequest:
    """This model stores attributes related to RP HTTP requests."""

    session_method: Callable
    url: Any
    files: Optional[Any]
    data: Optional[Any]
    json: Optional[Any]
    verify_ssl: Optional[Union[bool, str]]
    http_timeout: Union[float, Tuple[float, float]]
    name: Optional[str]
    _priority: Priority

    def __init__(self,
                 session_method: Callable,
                 url: Any,
                 data: Optional[Any] = None,
                 json: Optional[Any] = None,
                 files: Optional[Any] = None,
                 verify_ssl: Optional[bool] = None,
                 http_timeout: Union[float, Tuple[float, float]] = (10, 10),
                 name: Optional[Text] = None) -> None:
        """Initialize instance attributes.

        :param session_method: Method of the requests.Session instance
        :param url:            Request URL
        :param data:           Dictionary, list of tuples, bytes, or file-like
                               object to send in the body of the request
        :param json:           JSON to be sent in the body of the request
        :param verify_ssl:     Is SSL certificate verification required
        :param http_timeout:   a float in seconds for connect and read
                               timeout. Use a Tuple to specific connect and
                               read separately.
        :param name:           request name
        """
        self.data = data
        self.files = files
        self.json = json
        self.session_method = session_method
        self.url = url
        self.verify_ssl = verify_ssl
        self.http_timeout = http_timeout
        self.name = name
        self._priority = DEFAULT_PRIORITY

    def __lt__(self, other) -> bool:
        """Priority protocol for the PriorityQueue."""
        return self.priority < other.priority

    @property
    def priority(self) -> Priority:
        """Get the priority of the request."""
        return self._priority

    @priority.setter
    def priority(self, value: Priority) -> None:
        """Set the priority of the request."""
        self._priority = value

    def make(self):
        """Make HTTP request to the Report Portal API."""
        try:
            return RPResponse(self.session_method(self.url, data=self.data, json=self.json, files=self.files,
                                                  verify=self.verify_ssl, timeout=self.http_timeout))
        except (KeyError, IOError, ValueError, TypeError) as exc:
            logger.warning(
                "Report Portal %s request failed",
                self.name,
                exc_info=exc
            )


class AsyncHttpRequest(HttpRequest):
    """This model stores attributes related to RP HTTP requests."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    async def make(self):
        """Make HTTP request to the Report Portal API."""
        ssl_config = self.verify_ssl
        if ssl_config and type(ssl_config) == str:
            ssl_context = ssl.create_default_context()
            ssl_context.load_cert_chain(ssl_config)
            ssl_config = ssl_context

        timeout = None
        if self.http_timeout:
            if type(self.http_timeout) == tuple:
                connect_timeout, read_timeout = self.http_timeout
            else:
                connect_timeout, read_timeout = self.http_timeout, self.http_timeout
            timeout = aiohttp.ClientTimeout(connect=connect_timeout, sock_read=read_timeout)

        data = self.data
        if self.files:
            data = self.files

        try:
            return RPResponse(await self.session_method(await await_if_necessary(self.url), data=data,
                                                        json=self.json, ssl=ssl_config, timeout=timeout))
        except (KeyError, IOError, ValueError, TypeError) as exc:
            logger.warning(
                "Report Portal %s request failed",
                self.name,
                exc_info=exc
            )


class RPRequestBase(metaclass=AbstractBaseClass):
    """Base class for the rest of the RP request models."""

    __metaclass__ = AbstractBaseClass

    @abstractmethod
    def payload(self) -> dict:
        """Abstract interface for getting HTTP request payload."""
        raise NotImplementedError('Payload interface is not implemented!')


@dataclass(frozen=True)
class LaunchStartRequest(RPRequestBase):
    """RP start launch request model.

    https://github.com/reportportal/documentation/blob/master/src/md/src/DevGuides/reporting.md#start-launch
    """
    name: str
    start_time: str
    attributes: Optional[Union[list, dict]] = None
    description: Optional[str] = None
    mode: str = 'default'
    rerun: bool = False
    rerun_of: str = None
    uuid: str = None

    @property
    def payload(self) -> dict:
        """Get HTTP payload for the request."""
        my_attributes = None
        if self.attributes and isinstance(self.attributes, dict):
            my_attributes = dict_to_payload(self.attributes)
        result = {
            'attributes': my_attributes,
            'description': self.description,
            'mode': self.mode,
            'name': self.name,
            'rerun': self.rerun,
            'rerunOf': self.rerun_of,
            'startTime': self.start_time
        }
        if self.uuid:
            result['uuid'] = self.uuid
        return result


@dataclass(frozen=True)
class LaunchFinishRequest(RPRequestBase):
    """RP finish launch request model.

    https://github.com/reportportal/documentation/blob/master/src/md/src/DevGuides/reporting.md#finish-launch
    """

    end_time: str
    status: Optional[Text] = None
    attributes: Optional[Union[list, dict]] = None
    description: Optional[str] = None

    @property
    def payload(self) -> dict:
        """Get HTTP payload for the request."""
        my_attributes = None
        if self.attributes and isinstance(self.attributes, dict):
            my_attributes = dict_to_payload(self.attributes)
        return {
            'attributes': my_attributes,
            'description': self.description,
            'endTime': self.end_time,
            'status': self.status
        }


@dataclass(frozen=True)
class ItemStartRequest(RPRequestBase):
    """RP start test item request model.

    https://github.com/reportportal/documentation/blob/master/src/md/src/DevGuides/reporting.md#start-rootsuite-item
    """
    attributes: Optional[Union[list, dict]]
    code_ref: Optional[Text]
    description: Optional[Text]
    has_stats: bool
    launch_uuid: Any
    name: str
    parameters: Optional[Union[list, dict]]
    retry: bool
    start_time: str
    test_case_id: Optional[Text]
    type_: str

    @staticmethod
    def create_request(**kwargs) -> dict:
        request = {
            'codeRef': kwargs.get('code_ref'),
            'description': kwargs.get('description'),
            'hasStats': kwargs.get('has_stats'),
            'name': kwargs['name'],
            'retry': kwargs.get('retry'),
            'startTime': kwargs['start_time'],
            'testCaseId': kwargs.get('test_case_id'),
            'type': kwargs['type'],
            'launchUuid': kwargs['launch_uuid']
        }
        if 'attributes' in kwargs:
            request['attributes'] = dict_to_payload(kwargs['attributes'])
        if 'parameters' in kwargs:
            request['parameters'] = dict_to_payload(kwargs['parameters'])
        return request

    @property
    def payload(self) -> dict:
        """Get HTTP payload for the request."""
        data = self.__dict__.copy()
        data['type'] = data.pop('type_')
        return ItemStartRequest.create_request(**data)


class ItemStartRequestAsync(ItemStartRequest):

    def __int__(self, *args, **kwargs) -> None:
        super.__init__(*args, **kwargs)

    @property
    async def payload(self) -> dict:
        """Get HTTP payload for the request."""
        data = self.__dict__.copy()
        data['type'] = data.pop('type_')
        data['launch_uuid'] = await_if_necessary(data.pop('launch_uuid'))
        return ItemStartRequest.create_request(**data)


@dataclass(frozen=True)
class ItemFinishRequest(RPRequestBase):
    """RP finish test item request model.

    https://github.com/reportportal/documentation/blob/master/src/md/src/DevGuides/reporting.md#finish-child-item
    """
    attributes: Optional[Union[list, dict]]
    description: str
    end_time: str
    is_skipped_an_issue: bool
    issue: Issue
    launch_uuid: Any
    status: str
    retry: bool

    @staticmethod
    def create_request(**kwargs) -> dict:
        request = {
            'description': kwargs.get('description'),
            'endTime': kwargs['end_time'],
            'launchUuid': kwargs['launch_uuid'],
            'status': kwargs.get('status'),
            'retry': kwargs.get('retry')
        }
        if 'attributes' in kwargs:
            request['attributes'] = dict_to_payload(kwargs['attributes'])

        if kwargs.get('issue') is None and (
                kwargs.get('status') is not None and kwargs.get('status').lower() == 'skipped'
        ) and not kwargs.get('is_skipped_an_issue'):
            issue_payload = {'issue_type': 'NOT_ISSUE'}
        elif kwargs.get('issue') is not None:
            issue_payload = kwargs.get('issue').payload
        else:
            issue_payload = None
        request['issue'] = issue_payload
        return request

    @property
    def payload(self) -> dict:
        """Get HTTP payload for the request."""
        return ItemFinishRequest.create_request(**self.__dict__)


class ItemFinishRequestAsync(ItemFinishRequest):

    def __int__(self, *args, **kwargs) -> None:
        super.__init__(*args, **kwargs)

    @property
    async def payload(self) -> dict:
        """Get HTTP payload for the request."""
        data = self.__dict__.copy()
        data['launch_uuid'] = await_if_necessary(data.pop('launch_uuid'))
        return ItemFinishRequest.create_request(**data)


@dataclass(frozen=True)
class RPRequestLog(RPRequestBase):
    """RP log save request model.

    https://github.com/reportportal/documentation/blob/master/src/md/src/DevGuides/reporting.md#save-single-log-without-attachment
    """
    launch_uuid: str
    time: str
    file: Optional[RPFile] = None
    item_uuid: Optional[Text] = None
    level: str = RP_LOG_LEVELS[40000]
    message: Optional[Text] = None

    def __file(self) -> dict:
        """Form file payload part of the payload."""
        if not self.file:
            return {}
        return {'file': {'name': self.file.name}}

    @property
    def payload(self) -> dict:
        """Get HTTP payload for the request."""
        payload = {
            'launchUuid': self.launch_uuid,
            'level': self.level,
            'message': self.message,
            'time': self.time,
            'itemUuid': self.item_uuid
        }
        payload.update(self.__file())
        return payload

    @property
    def multipart_size(self) -> int:
        """Calculate request size how it would transfer in Multipart HTTP."""
        size = helpers.calculate_json_part_size(self.payload)
        size += helpers.calculate_file_part_size(self.file)
        return size


class RPLogBatch(RPRequestBase):
    """RP log save batches with attachments request model.

    https://github.com/reportportal/documentation/blob/master/src/md/src/DevGuides/reporting.md#batch-save-logs
    """
    default_content: str = ...
    log_reqs: List[RPRequestLog] = ...

    def __init__(self, log_reqs: List[RPRequestLog]) -> None:
        """Initialize instance attributes.

        :param log_reqs:
        """
        super().__init__()
        self.default_content = 'application/octet-stream'
        self.log_reqs = log_reqs
        self.priority = LOW_PRIORITY

    def __get_file(self, rp_file) -> Tuple[str, tuple]:
        """Form a tuple for the single file."""
        return ('file', (rp_file.name,
                         rp_file.content,
                         rp_file.content_type or self.default_content))

    def __get_files(self) -> List[Tuple[str, tuple]]:
        """Get list of files for the JSON body."""
        files = []
        for req in self.log_reqs:
            if req.file:
                files.append(self.__get_file(req.file))
        return files

    def __get_request_part(self) -> List[Tuple[str, tuple]]:
        r"""Form JSON body for the request.

        Example:
        [('json_request_part',
          (None,
           '[{"launchUuid": "bf6edb74-b092-4b32-993a-29967904a5b4",
              "time": "1588936537081",
              "message": "Html report",
              "level": "INFO",
              "itemUuid": "d9dc2514-2c78-4c4f-9369-ee4bca4c78f8",
              "file": {"name": "Detailed report"}}]',
           'application/json')),
         ('file',
          ('Detailed report',
           '<html lang="utf-8">\n<body><p>Paragraph</p></body></html>',
           'text/html'))]
        """
        body = [(
            'json_request_part', (
                None,
                json_converter.dumps([log.payload for log in self.log_reqs]),
                'application/json'
            )
        )]
        body.extend(self.__get_files())
        return body

    @property
    def payload(self) -> List[Tuple[str, tuple]]:
        """Get HTTP payload for the request."""
        return self.__get_request_part()
