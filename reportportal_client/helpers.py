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
import fnmatch
import inspect
import logging
import re
import threading
import time
import unicodedata
import uuid
from platform import machine, processor, system
from types import MappingProxyType
from typing import Any, Callable, Dict, Generic, Iterable, List, Optional, Tuple, TypeVar, Union

from reportportal_client.core.rp_file import RPFile

try:
    # noinspection PyPackageRequirements
    import simplejson as json
except ImportError:
    import json

logger: logging.Logger = logging.getLogger(__name__)
_T = TypeVar("_T")
ATTRIBUTE_LENGTH_LIMIT: int = 128
TRUNCATE_REPLACEMENT: str = "..."
BYTES_TO_READ_FOR_DETECTION = 128

CONTENT_TYPE_TO_EXTENSIONS = MappingProxyType(
    {
        "application/pdf": "pdf",
        "application/zip": "zip",
        "application/java-archive": "jar",
        "image/jpeg": "jpg",
        "image/png": "png",
        "image/gif": "gif",
        "image/bmp": "bmp",
        "image/vnd.microsoft.icon": "ico",
        "image/webp": "webp",
        "audio/mpeg": "mp3",
        "audio/wav": "wav",
        "video/mpeg": "mpeg",
        "video/avi": "avi",
        "video/webm": "webm",
        "text/plain": "txt",
        "application/octet-stream": "bin",
    }
)

PATTERN_MATCHES_EMPTY_STRING: re.Pattern = re.compile("^$")


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
        del state["_lock"]
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


def dict_to_payload(dictionary: Optional[dict]) -> Optional[List[dict]]:
    """Convert incoming dictionary to the list of dictionaries.

    This function transforms the given dictionary of tags/attributes into
    the format required by the ReportPortal API. Also, we add the system
    key to every tag/attribute that indicates that the key should be hidden
    from the user in UI.
    :param dictionary:  Dictionary containing tags/attributes
    :return list:       List of tags/attributes in the required format
    """
    if dictionary is None:
        return dictionary
    my_dictionary = dict(dictionary)

    hidden = my_dictionary.pop("system", None)
    result = []
    for key, value in sorted(my_dictionary.items()):
        attribute = {"key": str(key), "value": str(value)}
        if hidden is not None:
            attribute["system"] = hidden
        result.append(attribute)
    return result


def gen_attributes(rp_attributes: Iterable[str]) -> List[Dict[str, str]]:
    """Generate list of attributes for the API request.

    Example of input list:
    ['tag_name:tag_value1', 'tag_value2']
    Output of the function for the given input list:
    [{'key': 'tag_name', 'value': 'tag_value1'}, {'value': 'tag_value2'}]

    :param rp_attributes: Iterable of attributes(tags)
    :return:              Correctly created list of dictionaries
                          to be passed to RP
    """
    attrs = []
    for rp_attr in rp_attributes:
        try:
            key, value = rp_attr.split(":")
            attr_dict = {"key": key, "value": value}
        except ValueError as exc:
            logger.debug(str(exc))
            attr_dict = {"value": rp_attr}

        if all(attr_dict.values()):
            attrs.append(attr_dict)
            continue
        logger.debug(f'Failed to process "{rp_attr}" attribute, attribute value should not be empty.')
    return attrs


def get_launch_sys_attrs() -> Dict[str, str]:
    """Generate attributes for the launch containing system information.

    :return: dict {'os': 'Windows',
                   'cpu': 'AMD',
                   'machine': 'Windows10_pc'}
    """
    return {
        "os": system(),
        "cpu": processor() or "unknown",
        "machine": machine(),
        "system": True,  # This one is the flag for RP to hide these attributes
    }


def get_package_parameters(package_name: str, parameters: List[str] = None) -> List[Optional[str]]:
    """Get parameters of the given package.

    :param package_name: Name of the package.
    :param parameters:   Wanted parameters.
    :return:             Parameter List.
    """
    result = []
    if not parameters:
        return result

    from importlib.metadata import PackageNotFoundError, distribution

    try:
        package_info = distribution(package_name)
    except PackageNotFoundError:
        return [None] * len(parameters)
    for param in parameters:
        result.append(package_info.metadata[param.lower()[:1].upper() + param.lower()[1:]])
    return result


def get_package_version(package_name: str) -> Optional[str]:
    """Get version of the given package.

    :param package_name: Name of the package.
    :return:             Version of the package.
    """
    return get_package_parameters(package_name, ["version"])[0]


def truncate_attribute_string(text: str) -> str:
    """Truncate a text if it's longer than allowed.

    :param text: Text to truncate.
    :return:     Truncated text.
    """
    truncation_length = len(TRUNCATE_REPLACEMENT)
    if len(text) > ATTRIBUTE_LENGTH_LIMIT and len(text) > truncation_length:
        return text[: ATTRIBUTE_LENGTH_LIMIT - truncation_length] + TRUNCATE_REPLACEMENT
    return text


def verify_value_length(attributes: Optional[Union[List[dict], dict]]) -> Optional[List[dict]]:
    """Verify length of the attribute value.

    The length of the attribute value should have size from '1' to '128'.
    Otherwise, HTTP response will return an error.
    Example of the input list:
    [{'key': 'tag_name', 'value': 'tag_value1'}, {'value': 'tag_value2'}]

    :param attributes: List of attributes(tags)
    :return:           List of attributes with corrected value length
    """
    if attributes is None:
        return

    my_attributes = attributes
    if isinstance(my_attributes, dict):
        my_attributes = dict_to_payload(my_attributes)

    result = []
    for pair in my_attributes:
        if not isinstance(pair, dict):
            continue
        attr_value = pair.get("value")
        if attr_value is None:
            continue
        truncated = {}
        truncated.update(pair)
        result.append(truncated)
        attr_key = pair.get("key")
        if attr_key:
            truncated["key"] = truncate_attribute_string(str(attr_key))
        truncated["value"] = truncate_attribute_string(str(attr_value))
    return result


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
    return "/".join(str(s).strip("/").strip("\\") for s in uri_parts)


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
    return "/" + uri_join(*uri_parts)


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


TYPICAL_MULTIPART_BOUNDARY: str = "--972dbca3abacfd01fb4aea0571532b52"
TYPICAL_JSON_PART_HEADER: str = (
    TYPICAL_MULTIPART_BOUNDARY
    + """\r
Content-Disposition: form-data; name="json_request_part"\r
Content-Type: application/json\r
\r
"""
)
TYPICAL_FILE_PART_HEADER: str = (
    TYPICAL_MULTIPART_BOUNDARY
    + """\r
Content-Disposition: form-data; name="file"; filename="{0}"\r
Content-Type: {1}\r
\r
"""
)
TYPICAL_JSON_PART_HEADER_LENGTH: int = len(TYPICAL_JSON_PART_HEADER)
TYPICAL_MULTIPART_FOOTER: str = "\r\n" + TYPICAL_MULTIPART_BOUNDARY + "--"
TYPICAL_MULTIPART_FOOTER_LENGTH: int = len(TYPICAL_MULTIPART_FOOTER)
TYPICAL_JSON_ARRAY: str = "[]"
TYPICAL_JSON_ARRAY_LENGTH: int = len(TYPICAL_JSON_ARRAY)
TYPICAL_JSON_ARRAY_ELEMENT: str = ","
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


def agent_name_version(attributes: Optional[Union[list, dict]] = None) -> Tuple[Optional[str], Optional[str]]:
    """Extract Agent name and version from given Launch attributes.

    :param attributes: Launch attributes as they provided to Start Launch call
    :return: Tuple of (agent name, version)
    """
    my_attributes = attributes
    if isinstance(my_attributes, dict):
        my_attributes = dict_to_payload(my_attributes)
    agent_name, agent_version = None, None
    agent_attribute = [a for a in my_attributes if a.get("key") == "agent"] if my_attributes else []
    if len(agent_attribute) > 0 and agent_attribute[0].get("value"):
        agent_name, agent_version = agent_attribute[0]["value"].split("|")
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


def is_binary(iterable: Union[bytes, bytearray, str]) -> bool:
    """Check if given iterable is binary.

    :param iterable: iterable to check
    :return: True if iterable contains binary bytes, False otherwise
    """
    if isinstance(iterable, str):
        byte_iterable = iterable.encode("utf-8")
    else:
        byte_iterable = iterable

    if 0x00 in byte_iterable:
        return True
    return False


def guess_content_type_from_bytes(data: Union[bytes, bytearray, List[int]]) -> str:
    """Guess content type from bytes.

    :param data: bytes or bytearray
    :return: content type
    """
    my_data = data
    if isinstance(data, list):
        my_data = bytes(my_data)

    if len(my_data) >= BYTES_TO_READ_FOR_DETECTION:
        my_data = my_data[:BYTES_TO_READ_FOR_DETECTION]

    if not is_binary(my_data):
        return "text/plain"

    # images
    if my_data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if my_data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if my_data.startswith(b"GIF8"):
        return "image/gif"
    if my_data.startswith(b"BM"):
        return "image/bmp"
    if my_data.startswith(b"\x00\x00\x01\x00"):
        return "image/vnd.microsoft.icon"
    if my_data.startswith(b"RIFF") and b"WEBP" in my_data:
        return "image/webp"

    # audio
    if my_data.startswith(b"ID3"):
        return "audio/mpeg"
    if my_data.startswith(b"RIFF") and b"WAVE" in my_data:
        return "audio/wav"

    # video
    if my_data.startswith(b"\x00\x00\x01\xba"):
        return "video/mpeg"
    if my_data.startswith(b"RIFF") and b"AVI LIST" in my_data:
        return "video/avi"
    if my_data.startswith(b"\x1aE\xdf\xa3"):
        return "video/webm"

    # archives
    if my_data.startswith(b"PK\x03\x04"):
        if my_data.startswith(b"PK\x03\x04\x14\x00\x08"):
            return "application/java-archive"
        return "application/zip"
    if my_data.startswith(b"PK\x05\x06"):
        return "application/zip"

    # office
    if my_data.startswith(b"%PDF"):
        return "application/pdf"

    return "application/octet-stream"


def to_bool(value: Optional[Any]) -> Optional[bool]:
    """Convert value of any type to boolean or raise ValueError.

    :param value: value to convert
    :return: boolean value
    :raises ValueError: if value is not boolean
    """
    if value is None:
        return None
    if value in {"TRUE", "True", "true", "1", "Y", "y", 1, True}:
        return True
    if value in {"FALSE", "False", "false", "0", "N", "n", 0, False}:
        return False
    raise ValueError(f"Invalid boolean value {value}.")


def translate_glob_to_regex(pattern: Optional[str]) -> Optional[re.Pattern]:
    """Translate glob string pattern to regex Pattern.

    :param pattern: glob pattern
    :return: regex pattern
    """
    if pattern is None:
        return None
    if pattern == "":
        return PATTERN_MATCHES_EMPTY_STRING
    return re.compile(fnmatch.translate(pattern))


def match_pattern(pattern: Optional[re.Pattern], line: Optional[str]) -> bool:
    """Check if the line matches given pattern. Handles None values.

    :param pattern: regex pattern
    :param line: line to check
    :return: True if the line matches the pattern, False otherwise
    """
    if pattern is None:
        return True
    if line is None:
        return False

    return pattern.fullmatch(line) is not None


def normalize_caseless(text: str) -> str:
    """Normalize and casefold the text.

    :param text: text to normalize
    :return: normalized text
    """
    return unicodedata.normalize("NFKD", text.casefold())


def caseless_equal(left: str, right: str) -> bool:
    """Check if two strings are equal ignoring case.

    :param left: left string
    :param right: right string
    :return: True if strings are equal ignoring case, False otherwise
    """
    return normalize_caseless(left) == normalize_caseless(right)
