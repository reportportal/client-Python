"""This module contains common functions-helpers of the client and agents.

Copyright (c) 2022 https://reportportal.io .
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at
https://www.apache.org/licenses/LICENSE-2.0
Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""
import inspect
import json
import logging
import time
import uuid
from platform import machine, processor, system

import six
from pkg_resources import DistributionNotFound, get_distribution

from .static.defines import ATTRIBUTE_LENGTH_LIMIT

logger = logging.getLogger(__name__)


def generate_uuid():
    """Generate UUID."""
    return str(uuid.uuid4())


def convert_string(value):
    """Support and convert strings in py2 and py3.

    :param value:   input string
    :return value:  converted string
    """
    if isinstance(value, six.text_type):
        # Don't try to encode 'unicode' in Python 2.
        return value
    return str(value)


def dict_to_payload(dictionary):
    """Convert incoming dictionary to the list of dictionaries.

    This function transforms the given dictionary of tags/attributes into
    the format required by the Report Portal API. Also, we add the system
    key to every tag/attribute that indicates that the key should be hidden
    from the user in UI.
    :param dictionary:  Dictionary containing tags/attributes
    :return list:       List of tags/attributes in the required format
    """
    hidden = dictionary.pop('system', False)
    return [
        {'key': key, 'value': convert_string(value), 'system': hidden}
        for key, value in sorted(dictionary.items())
    ]


def gen_attributes(rp_attributes):
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


def get_launch_sys_attrs():
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


def get_package_version(package_name):
    """Get version of the given package.

    :param package_name: Name of the package
    :return:             Version of the package
    """
    try:
        package_version = get_distribution(package_name).version
    except DistributionNotFound:
        package_version = 'not found'
    return package_version


def verify_value_length(attributes):
    """Verify length of the attribute value.

    The length of the attribute value should have size from '1' to '128'.
    Otherwise HTTP response will return an error.
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


def timestamp():
    """Return string representation of the current time in milliseconds."""
    return str(int(time.time() * 1000))


def uri_join(*uri_parts):
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


def get_function_params(func, args, kwargs):
    """Extract argument names from the function and combine them with values.

    :param func: the function to get arg names
    :param args: function's arg values
    :param kwargs: function's kwargs
    :return: a dictionary of values
    """
    if six.PY2:
        # Use deprecated method for python 2.7 compatibility
        arg_spec = inspect.getargspec(func)
    else:
        arg_spec = inspect.getfullargspec(func)
    result = dict()
    for i, arg_name in enumerate(arg_spec.args):
        if i >= len(args):
            break
        result[arg_name] = args[i]
    for arg_name, arg_value in kwargs.items():
        result[arg_name] = arg_value
    return result if len(result.items()) > 0 else None


TYPICAL_MULTIPART_BOUNDARY = '--972dbca3abacfd01fb4aea0571532b52'

TYPICAL_JSON_PART_HEADER = TYPICAL_MULTIPART_BOUNDARY + '''\r
Content-Disposition: form-data; name="json_request_part"\r
Content-Type: application/json\r
\r
'''

TYPICAL_FILE_PART_HEADER = TYPICAL_MULTIPART_BOUNDARY + '''\r
Content-Disposition: form-data; name="file"; filename="{0}"\r
Content-Type: {1}\r
\r
'''

TYPICAL_JSON_PART_HEADER_LENGTH = len(TYPICAL_JSON_PART_HEADER)

TYPICAL_MULTIPART_FOOTER = '\r\n' + TYPICAL_MULTIPART_BOUNDARY + '--'

TYPICAL_MULTIPART_FOOTER_LENGTH = len(TYPICAL_MULTIPART_FOOTER)

TYPICAL_JSON_ARRAY = '[]'

TYPICAL_JSON_ARRAY_LENGTH = len(TYPICAL_JSON_ARRAY)

TYPICAL_JSON_ARRAY_ELEMENT = ','

TYPICAL_JSON_ARRAY_ELEMENT_LENGTH = len(TYPICAL_JSON_ARRAY_ELEMENT)


def calculate_json_part_size(json_dict):
    """Predict a JSON part size of Multipart request.

    :param json_dict: a dictionary representing the JSON
    :return:          Multipart request part size
    """
    size = len(json.dumps(json_dict))
    size += TYPICAL_JSON_PART_HEADER_LENGTH
    size += TYPICAL_JSON_ARRAY_LENGTH
    size += TYPICAL_JSON_ARRAY_ELEMENT_LENGTH
    return size


def calculate_file_part_size(file):
    """Predict a file part size of Multipart request.

    :param file: RPFile class instance
    :return:     Multipart request part size
    """
    if file is None:
        return 0
    size = len(TYPICAL_FILE_PART_HEADER.format(file.name, file.content_type))
    size += len(file.content)
    return size
