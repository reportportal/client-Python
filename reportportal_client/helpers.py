"""This module contains common functions-helpers of the client and agents.

Copyright (c) 2018 http://reportportal.io .
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at
http://www.apache.org/licenses/LICENSE-2.0
Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""
import logging
import time
import uuid
from platform import machine, processor, system

import six
from pkg_resources import DistributionNotFound, get_distribution

from .errors import ResponseError, EntryCreatedError, OperationCompletionError
from .static.defines import ATTRIBUTE_LENGTH_LIMIT

logger = logging.getLogger(__name__)


def generate_uuid():
    """Generate Uuid."""
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
    """Convert dict to list of dicts.

    :param dictionary:  initial dict
    :return list:       list of dicts
    """
    system = dictionary.pop('system', False)
    return [
        {'key': key, 'value': convert_string(value), 'system': system}
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


def get_id(response):
    """Get id from Response.

    :param response: Response object
    :return id: int value of id
    """
    try:
        return get_data(response)["id"]
    except KeyError:
        raise EntryCreatedError(
            "No 'id' in response: {0}".format(response.text))


def get_msg(response):
    """
    Get message from Response.

    :param response: Response object
    :return: data: json data
    """
    try:
        return get_data(response)
    except KeyError:
        raise OperationCompletionError(
            "No 'message' in response: {0}".format(response.text))


def get_data(response):
    """
    Get data from Response.

    :param response: Response object
    :return: json data
    """
    data = get_json(response)
    error_messages = get_error_messages(data)
    error_count = len(error_messages)

    if error_count == 1:
        raise ResponseError(error_messages[0])
    elif error_count > 1:
        raise ResponseError(
            "\n  - ".join(["Multiple errors:"] + error_messages))
    elif not response.ok:
        response.raise_for_status()
    elif not data:
        raise ResponseError("Empty response")
    else:
        return data


def get_json(response):
    """
    Get json from Response.

    :param response: Response object
    :return: data: json object
    """
    try:
        if response.text:
            return response.json()
        else:
            return {}
    except ValueError as value_error:
        raise ResponseError(
            "Invalid response: {0}: {1}".format(value_error, response.text))


def get_error_messages(data):
    """
    Get messages (ErrorCode) from Response.

    :param data: dict of datas
    :return list: Empty list or list of errors
    """
    error_messages = []
    for ret in data.get("responses", [data]):
        if "errorCode" in ret:
            error_messages.append(
                "{0}: {1}".format(ret["errorCode"], ret.get("message"))
            )

    return error_messages
