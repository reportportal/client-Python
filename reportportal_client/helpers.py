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

"""This module contains common functions-helpers of the client and agents."""

import asyncio
import inspect
import json
import logging
import queue
import threading
import time
import uuid
from platform import machine, processor, system
from typing import Optional, Any, List, Dict, Callable, Tuple, Union, TypeVar, Generic

from pkg_resources import DistributionNotFound, get_distribution

from reportportal_client.core.rp_file import RPFile
from reportportal_client.static.defines import ATTRIBUTE_LENGTH_LIMIT

logger: logging.Logger = logging.getLogger(__name__)
_T = TypeVar('_T')


class LifoQueue(Generic[_T]):
    """Primitive thread-safe Last-in-first-out queue implementation."""

    _lock: threading.Lock()
    __items: List[_T]

    def __init__(self):
        """Initialize the queue instance."""
        self._lock = threading.Lock()
        self.__items = []

    def put(self, element: _T) -> None:
        """Add an element to the queue."""
        with self._lock:
            self.__items.append(element)

    def get(self) -> Optional[_T]:
        """Return and remove the last element from the queue.

        :return: The last element in the queue.
        """
        result = None
        with self._lock:
            if len(self.__items) > 0:
                result = self.__items[-1]
                self.__items = self.__items[:-1]
        return result

    def last(self) -> _T:
        """Return the last element from the queue, but does not remove it.

        :return: The last element in the queue.
        """
        with self._lock:
            if len(self.__items) > 0:
                return self.__items[-1]

    def qsize(self):
        """Return the queue size."""
        with self._lock:
            return len(self.__items)

    def __getstate__(self) -> Dict[str, Any]:
        """Control object pickling and return object fields as Dictionary.

        :return: object state dictionary
        :rtype: dict
        """
        state = self.__dict__.copy()
        # Don't pickle 'session' field, since it contains unpickling 'socket'
        del state['_lock']
        return state

    def __setstate__(self, state: Dict[str, Any]) -> None:
        """Control object pickling, receives object state as Dictionary.

        :param dict state: object state dictionary
        """
        self.__dict__.update(state)
        self._lock = threading.Lock()


def generate_uuid() -> str:
    """Generate UUID."""
    return str(uuid.uuid4())


def dict_to_payload(dictionary: dict) -> List[dict]:
    """Convert incoming dictionary to the list of dictionaries.

    This function transforms the given dictionary of tags/attributes into
    the format required by the ReportPortal API. Also, we add the system
    key to every tag/attribute that indicates that the key should be hidden
    from the user in UI.
    :param dictionary:  Dictionary containing tags/attributes
    :return list:       List of tags/attributes in the required format
    """
    hidden = dictionary.pop('system', False)
    return [
        {'key': key, 'value': str(value), 'system': hidden}
        for key, value in sorted(dictionary.items())
    ]


def gen_attributes(rp_attributes: List[str]) -> List[Dict[str, str]]:
    """Generate list of attributes for the API request.

    Example of input list:
    ['tag_name:tag_value1', 'tag_value2']
    Output of the function for the given input list:
    [{'key': 'tag_name', 'value': 'tag_value1'}, {'value': 'tag_value2'}]

    :param rp_attributes: List of attributes(tags)
    :return:              Correctly created list of dictionaries
                          to be passed to RP
    """
    attrs = []
    for rp_attr in rp_attributes:
        try:
            key, value = rp_attr.split(':')
            attr_dict = {'key': key, 'value': value}
        except ValueError as exc:
            logger.debug(str(exc))
            attr_dict = {'value': rp_attr}

        if all(attr_dict.values()):
            attrs.append(attr_dict)
            continue
        logger.debug('Failed to process "{0}" attribute, attribute value'
                     ' should not be empty.'.format(rp_attr))
    return attrs


def get_launch_sys_attrs() -> Dict[str, str]:
    """Generate attributes for the launch containing system information.

    :return: dict {'os': 'Windows',
                   'cpu': 'AMD',
                   'machine': 'Windows10_pc'}
    """
    return {
        'os': system(),
        'cpu': processor() or 'unknown',
        'machine': machine(),
        'system': True  # This one is the flag for RP to hide these attributes
    }


def get_package_version(package_name) -> str:
    """Get version of the given package.

    :param package_name: Name of the package
    :return:             Version of the package
    """
    try:
        package_version = get_distribution(package_name).version
    except DistributionNotFound:
        package_version = 'not found'
    return package_version


def verify_value_length(attributes: List[dict]) -> List[dict]:
    """Verify length of the attribute value.

    The length of the attribute value should have size from '1' to '128'.
    Otherwise, HTTP response will return an error.
    Example of the input list:
    [{'key': 'tag_name', 'value': 'tag_value1'}, {'value': 'tag_value2'}]
    :param attributes: List of attributes(tags)
    :return:           List of attributes with corrected value length
    """
    if attributes is not None:
        for pair in attributes:
            if not isinstance(pair, dict):
                continue
            attr_value = pair.get('value')
            if attr_value is None:
                continue
            try:
                pair['value'] = attr_value[:ATTRIBUTE_LENGTH_LIMIT]
            except TypeError:
                continue
    return attributes


def timestamp() -> str:
    """Return string representation of the current time in milliseconds."""
    return str(int(time.time() * 1000))


def uri_join(*uri_parts: str) -> str:
    """Join uri parts.

    Avoiding usage of urlparse.urljoin and os.path.join
    as it does not clearly join parts.
    Args:
        *uri_parts: tuple of values for join, can contain back and forward
                    slashes (will be stripped up).
    Returns:
        An uri string.
    """
    return '/'.join(str(s).strip('/').strip('\\') for s in uri_parts)


def root_uri_join(*uri_parts: str) -> str:
    """Join uri parts. Format it as path from server root.

    Avoiding usage of urlparse.urljoin and os.path.join
    as it does not clearly join parts.
    Args:
        *uri_parts: tuple of values for join, can contain back and forward
                    slashes (will be stripped up).
    Returns:
        An uri string.
    """
    return '/' + uri_join(*uri_parts)


def get_function_params(func: Callable, args: tuple, kwargs: Dict[str, Any]) -> Dict[str, Any]:
    """Extract argument names from the function and combine them with values.

    :param func: the function to get arg names
    :param args: function's arg values
    :param kwargs: function's kwargs
    :return: a dictionary of values
    """
    arg_spec = inspect.getfullargspec(func)
    result = dict()
    for i, arg_name in enumerate(arg_spec.args):
        if i >= len(args):
            break
        result[arg_name] = args[i]
    for arg_name, arg_value in kwargs.items():
        result[arg_name] = arg_value
    return result if len(result.items()) > 0 else None


TYPICAL_MULTIPART_BOUNDARY: str = '--972dbca3abacfd01fb4aea0571532b52'

TYPICAL_JSON_PART_HEADER: str = TYPICAL_MULTIPART_BOUNDARY + '''\r
Content-Disposition: form-data; name="json_request_part"\r
Content-Type: application/json\r
\r
'''

TYPICAL_FILE_PART_HEADER: str = TYPICAL_MULTIPART_BOUNDARY + '''\r
Content-Disposition: form-data; name="file"; filename="{0}"\r
Content-Type: {1}\r
\r
'''

TYPICAL_JSON_PART_HEADER_LENGTH: int = len(TYPICAL_JSON_PART_HEADER)

TYPICAL_MULTIPART_FOOTER: str = '\r\n' + TYPICAL_MULTIPART_BOUNDARY + '--'

TYPICAL_MULTIPART_FOOTER_LENGTH: int = len(TYPICAL_MULTIPART_FOOTER)

TYPICAL_JSON_ARRAY: str = '[]'

TYPICAL_JSON_ARRAY_LENGTH: int = len(TYPICAL_JSON_ARRAY)

TYPICAL_JSON_ARRAY_ELEMENT: str = ','

TYPICAL_JSON_ARRAY_ELEMENT_LENGTH: int = len(TYPICAL_JSON_ARRAY_ELEMENT)


def calculate_json_part_size(json_dict: dict) -> int:
    """Predict a JSON part size of Multipart request.

    :param json_dict: a dictionary representing the JSON
    :return:          Multipart request part size
    """
    size = len(json.dumps(json_dict))
    size += TYPICAL_JSON_PART_HEADER_LENGTH
    size += TYPICAL_JSON_ARRAY_LENGTH
    size += TYPICAL_JSON_ARRAY_ELEMENT_LENGTH
    return size


def calculate_file_part_size(file: Optional[RPFile]) -> int:
    """Predict a file part size of Multipart request.

    :param file: RPFile class instance
    :return:     Multipart request part size
    """
    if file is None:
        return 0
    size = len(TYPICAL_FILE_PART_HEADER.format(file.name, file.content_type))
    size += len(file.content)
    return size


def agent_name_version(attributes: Optional[Union[List, Dict]] = None) -> Tuple[Optional[str], Optional[str]]:
    """Extract Agent name and version from given Launch attributes.

    :param attributes: Launch attributes as they provided to Start Launch call
    :return: Tuple of (agent name, version)
    """
    agent_name, agent_version = None, None
    agent_attribute = [a for a in attributes if a.get('key') == 'agent'] if attributes else []
    if len(agent_attribute) > 0 and agent_attribute[0].get('value'):
        agent_name, agent_version = agent_attribute[0]['value'].split('|')
    return agent_name, agent_version


async def await_if_necessary(obj: Optional[Any]) -> Optional[Any]:
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
