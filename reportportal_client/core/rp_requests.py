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

"""This module includes classes representing ReportPortal API requests.

Detailed information about requests wrapped up in that module
can be found by the following link:
https://github.com/reportportal/documentation/blob/master/src/md/src/DevGuides/reporting.md
"""

import asyncio
import json as json_converter
import logging
from dataclasses import dataclass
from typing import Callable, Optional, Union, List, Tuple, Any, TypeVar

import aiohttp

from reportportal_client import helpers
# noinspection PyProtectedMember
from reportportal_client._internal.static.abstract import (
    AbstractBaseClass,
    abstractmethod
)
# noinspection PyProtectedMember
from reportportal_client._internal.static.defines import (
    DEFAULT_PRIORITY,
    LOW_PRIORITY,
    RP_LOG_LEVELS, Priority
)
from reportportal_client.core.rp_file import RPFile
from reportportal_client.core.rp_issues import Issue
from reportportal_client.core.rp_responses import RPResponse, AsyncRPResponse
from reportportal_client.helpers import dict_to_payload, await_if_necessary

logger = logging.getLogger(__name__)
T = TypeVar("T")


class HttpRequest:
    """This model stores attributes related to ReportPortal HTTP requests."""

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
                 verify_ssl: Optional[Union[bool, str]] = None,
                 http_timeout: Union[float, Tuple[float, float]] = (10, 10),
                 name: Optional[str] = None) -> None:
        """Initialize an instance of the request with attributes.

        :param session_method: Method of the requests.Session instance
        :param url:            Request URL
        :param data:           Dictionary, list of tuples, bytes, or file-like object to send in the body of
                               the request
        :param json:           JSON to be sent in the body of the request
        :param files           Dictionary for multipart encoding upload
        :param verify_ssl:     Is SSL certificate verification required
        :param http_timeout:   a float in seconds for connect and read timeout. Use a Tuple to specific
                               connect and read separately
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

    def __lt__(self, other: 'HttpRequest') -> bool:
        """Priority protocol for the PriorityQueue.

        :param other: another object to compare
        :return:      if current object is less than other
        """
        return self.priority < other.priority

    @property
    def priority(self) -> Priority:
        """Get the priority of the request.

        :return: the object priority
        """
        return self._priority

    @priority.setter
    def priority(self, value: Priority) -> None:
        """Set the priority of the request.

        :param value: the object priority
        """
        self._priority = value

    def make(self) -> Optional[RPResponse]:
        """Make HTTP request to the ReportPortal API.

        The method catches any request preparation error to not fail reporting. Since we are reporting tool
        and should not fail tests.

        :return: wrapped HTTP response or None in case of failure
        """
        try:
            return RPResponse(self.session_method(self.url, data=self.data, json=self.json, files=self.files,
                                                  verify=self.verify_ssl, timeout=self.http_timeout))
        except (KeyError, IOError, ValueError, TypeError) as exc:
            logger.warning("ReportPortal %s request failed", self.name, exc_info=exc)


class AsyncHttpRequest(HttpRequest):
    """This model stores attributes related to asynchronous ReportPortal HTTP requests."""

    def __init__(self,
                 session_method: Callable,
                 url: Any,
                 data: Optional[Any] = None,
                 json: Optional[Any] = None,
                 name: Optional[str] = None) -> None:
        """Initialize an instance of the request with attributes.

        :param session_method: Method of the requests.Session instance
        :param url:            Request URL or async coroutine returning the URL
        :param data:           Dictionary, list of tuples, bytes, or file-like object, or async coroutine to
                               send in the body of the request
        :param json:           JSON to be sent in the body of the request as Dictionary or async coroutine
        :param name:           request name
        """
        super().__init__(session_method=session_method, url=url, data=data, json=json, name=name)

    async def make(self) -> Optional[AsyncRPResponse]:
        """Asynchronously make HTTP request to the ReportPortal API.

        The method catches any request preparation error to not fail reporting. Since we are reporting tool
        and should not fail tests.

        :return: wrapped HTTP response or None in case of failure
        """
        url = await await_if_necessary(self.url)
        if not url:
            return
        data = await await_if_necessary(self.data)
        json = await await_if_necessary(self.json)
        try:
            return AsyncRPResponse(await self.session_method(url, data=data, json=json))
        except (KeyError, IOError, ValueError, TypeError) as exc:
            logger.warning("ReportPortal %s request failed", self.name, exc_info=exc)


class RPRequestBase(metaclass=AbstractBaseClass):
    """Base class for specific ReportPortal request models.

    Its main function to provide interface of 'payload' method which is used to generate HTTP request payload.
    """

    __metaclass__ = AbstractBaseClass

    @property
    @abstractmethod
    def payload(self) -> dict:
        """Abstract interface for getting HTTP request payload.

        :return: JSON representation in the form of a Dictionary
        """
        raise NotImplementedError('Payload interface is not implemented!')


@dataclass(frozen=True)
class LaunchStartRequest(RPRequestBase):
    """ReportPortal start launch request model.

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
        """Get HTTP payload for the request.

        :return: JSON representation in the form of a Dictionary
        """
        my_attributes = self.attributes
        if my_attributes and isinstance(self.attributes, dict):
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
    """ReportPortal finish launch request model.

    https://github.com/reportportal/documentation/blob/master/src/md/src/DevGuides/reporting.md#finish-launch
    """

    end_time: str
    status: Optional[str] = None
    attributes: Optional[Union[list, dict]] = None
    description: Optional[str] = None

    @property
    def payload(self) -> dict:
        """Get HTTP payload for the request.

        :return: JSON representation in the form of a Dictionary
        """
        my_attributes = self.attributes
        if my_attributes and isinstance(self.attributes, dict):
            my_attributes = dict_to_payload(self.attributes)
        return {
            'attributes': my_attributes,
            'description': self.description,
            'endTime': self.end_time,
            'status': self.status
        }


@dataclass(frozen=True)
class ItemStartRequest(RPRequestBase):
    """ReportPortal start test item request model.

    https://github.com/reportportal/documentation/blob/master/src/md/src/DevGuides/reporting.md#start-rootsuite-item
    """

    name: str
    start_time: str
    type_: str
    launch_uuid: Any
    attributes: Optional[Union[list, dict]]
    code_ref: Optional[str]
    description: Optional[str]
    has_stats: bool
    parameters: Optional[Union[list, dict]]
    retry: bool
    test_case_id: Optional[str]

    @staticmethod
    def _create_request(**kwargs) -> dict:
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
        attributes = kwargs.get('attributes')
        if attributes and isinstance(attributes, dict):
            attributes = dict_to_payload(kwargs['attributes'])
        request['attributes'] = attributes
        parameters = kwargs.get('parameters')
        if parameters and isinstance(parameters, dict):
            parameters = dict_to_payload(kwargs['parameters'])
        request['parameters'] = parameters
        return request

    @property
    def payload(self) -> dict:
        """Get HTTP payload for the request.

        :return: JSON representation in the form of a Dictionary
        """
        data = self.__dict__.copy()
        data['type'] = data.pop('type_')
        return ItemStartRequest._create_request(**data)


class AsyncItemStartRequest(ItemStartRequest):
    """ReportPortal start test item request asynchronous model.

    https://github.com/reportportal/documentation/blob/master/src/md/src/DevGuides/reporting.md#start-rootsuite-item
    """

    def __int__(self, *args, **kwargs) -> None:
        """Initialize an instance of the request with attributes."""
        super.__init__(*args, **kwargs)

    @property
    async def payload(self) -> dict:
        """Get HTTP payload for the request.

        :return: JSON representation in the form of a Dictionary
        """
        data = self.__dict__.copy()
        data['type'] = data.pop('type_')
        data['launch_uuid'] = await await_if_necessary(data.pop('launch_uuid'))
        return ItemStartRequest._create_request(**data)


@dataclass(frozen=True)
class ItemFinishRequest(RPRequestBase):
    """ReportPortal finish test item request model.

    https://github.com/reportportal/documentation/blob/master/src/md/src/DevGuides/reporting.md#finish-child-item
    """

    end_time: str
    launch_uuid: Any
    status: str
    attributes: Optional[Union[list, dict]]
    description: str
    is_skipped_an_issue: bool
    issue: Issue
    retry: bool

    @staticmethod
    def _create_request(**kwargs) -> dict:
        request = {
            'description': kwargs.get('description'),
            'endTime': kwargs['end_time'],
            'launchUuid': kwargs['launch_uuid'],
            'status': kwargs.get('status'),
            'retry': kwargs.get('retry')
        }
        attributes = kwargs.get('attributes')
        if attributes and isinstance(attributes, dict):
            attributes = dict_to_payload(kwargs['attributes'])
        request['attributes'] = attributes

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
        """Get HTTP payload for the request.

        :return: JSON representation in the form of a Dictionary
        """
        return ItemFinishRequest._create_request(**self.__dict__)


class AsyncItemFinishRequest(ItemFinishRequest):
    """ReportPortal finish test item request asynchronous model.

    https://github.com/reportportal/documentation/blob/master/src/md/src/DevGuides/reporting.md#finish-child-item
    """

    def __int__(self, *args, **kwargs) -> None:
        """Initialize an instance of the request with attributes."""
        super.__init__(*args, **kwargs)

    @property
    async def payload(self) -> dict:
        """Get HTTP payload for the request.

        :return: JSON representation in the form of a Dictionary
        """
        data = self.__dict__.copy()
        data['launch_uuid'] = await await_if_necessary(data.pop('launch_uuid'))
        return ItemFinishRequest._create_request(**data)


@dataclass(frozen=True)
class RPRequestLog(RPRequestBase):
    """ReportPortal log save request model.

    https://github.com/reportportal/documentation/blob/master/src/md/src/DevGuides/reporting.md#save-single-log-without-attachment
    """

    launch_uuid: Any
    time: str
    file: Optional[RPFile] = None
    item_uuid: Optional[Any] = None
    level: str = RP_LOG_LEVELS[40000]
    message: Optional[str] = None

    @staticmethod
    def _create_request(**kwargs) -> dict:
        request = {
            'launchUuid': kwargs['launch_uuid'],
            'level': kwargs['level'],
            'message': kwargs.get('message'),
            'time': kwargs['time'],
            'itemUuid': kwargs.get('item_uuid'),
            'file': kwargs.get('file')
        }
        if 'file' in kwargs and kwargs['file']:
            request['file'] = {'name': kwargs['file'].name}
        return request

    @property
    def payload(self) -> dict:
        """Get HTTP payload for the request.

        :return: JSON representation in the form of a Dictionary
        """
        return RPRequestLog._create_request(**self.__dict__)

    @staticmethod
    def _multipart_size(payload: dict, file: Optional[RPFile]):
        size = helpers.calculate_json_part_size(payload)
        size += helpers.calculate_file_part_size(file)
        return size

    @property
    def multipart_size(self) -> int:
        """Calculate request size how it would be transfer in Multipart HTTP.

        :return: estimate request size
        """
        return RPRequestLog._multipart_size(self.payload, self.file)


class AsyncRPRequestLog(RPRequestLog):
    """ReportPortal log save request asynchronous model.

    https://github.com/reportportal/documentation/blob/master/src/md/src/DevGuides/reporting.md#save-single-log-without-attachment
    """

    def __int__(self, *args, **kwargs) -> None:
        """Initialize an instance of the request with attributes."""
        super.__init__(*args, **kwargs)

    @property
    async def payload(self) -> dict:
        """Get HTTP payload for the request.

        :return: JSON representation in the form of a Dictionary
        """
        data = self.__dict__.copy()
        uuids = await asyncio.gather(await_if_necessary(data.pop('launch_uuid')),
                                     await_if_necessary(data.pop('item_uuid')))
        data['launch_uuid'] = uuids[0]
        data['item_uuid'] = uuids[1]
        return RPRequestLog._create_request(**data)

    @property
    async def multipart_size(self) -> int:
        """Calculate request size how it would be transfer in Multipart HTTP.

        :return: estimate request size
        """
        return RPRequestLog._multipart_size(await self.payload, self.file)


class RPLogBatch(RPRequestBase):
    """ReportPortal log save batches with attachments request model.

    https://github.com/reportportal/documentation/blob/master/src/md/src/DevGuides/reporting.md#batch-save-logs
    """

    default_content: str
    log_reqs: List[Union[RPRequestLog, AsyncRPRequestLog]]
    priority: Priority

    def __init__(self, log_reqs: List[Union[RPRequestLog, AsyncRPRequestLog]]) -> None:
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

    def _get_files(self) -> List[Tuple[str, tuple]]:
        """Get list of files for the JSON body."""
        files = []
        for req in self.log_reqs:
            if req.file:
                files.append(self.__get_file(req.file))
        return files

    def __get_request_part(self) -> List[Tuple[str, tuple]]:
        body = [(
            'json_request_part', (
                None,
                json_converter.dumps([log.payload for log in self.log_reqs]),
                'application/json'
            )
        )]
        return body

    @property
    def payload(self) -> List[Tuple[str, tuple]]:
        r"""Get HTTP payload for the request.

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
        body = self.__get_request_part()
        body.extend(self._get_files())
        return body


class AsyncRPLogBatch(RPLogBatch):
    """ReportPortal log save batches with attachments request asynchronous model.

    https://github.com/reportportal/documentation/blob/master/src/md/src/DevGuides/reporting.md#batch-save-logs
    """

    def __int__(self, *args, **kwargs) -> None:
        """Initialize an instance of the request with attributes."""
        super.__init__(*args, **kwargs)

    async def __get_request_part(self) -> List[dict]:
        coroutines = [log.payload for log in self.log_reqs]
        return list(await asyncio.gather(*coroutines))

    @property
    async def payload(self) -> aiohttp.MultipartWriter:
        """Get HTTP payload for the request.

        :return: Multipart request object capable to send with AIOHTTP
        """
        json_payload = aiohttp.JsonPayload(await self.__get_request_part())
        json_payload.set_content_disposition('form-data', name='json_request_part')
        mp_writer = aiohttp.MultipartWriter('form-data')
        mp_writer.append_payload(json_payload)
        for _, file in self._get_files():
            file_payload = aiohttp.BytesPayload(file[1], content_type=file[2])
            file_payload.set_content_disposition('form-data', name='file', filename=file[0])
            mp_writer.append_payload(file_payload)
        return mp_writer
