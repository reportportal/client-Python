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

"""This script contains unit tests for the helpers script."""

from unittest import mock

# noinspection PyPackageRequirements
import pytest

from reportportal_client.helpers import (
    gen_attributes,
    get_launch_sys_attrs,
    verify_value_length, ATTRIBUTE_LENGTH_LIMIT, TRUNCATE_REPLACEMENT, guess_content_type_from_bytes, is_binary
)


def test_gen_attributes():
    """Test functionality of the gen_attributes function."""
    expected_out = [{'value': 'Tag'}, {'key': 'Key', 'value': 'Value'}]
    out = gen_attributes(['Tag', 'Key:Value', ''])
    assert expected_out == out


@mock.patch('reportportal_client.helpers.system',
            mock.Mock(return_value='linux'))
@mock.patch('reportportal_client.helpers.machine',
            mock.Mock(return_value='Windows-PC'))
@mock.patch('reportportal_client.helpers.processor',
            mock.Mock(return_value='amd'))
def test_get_launch_sys_attrs():
    """Test for validate get_launch_sys_attrs function."""
    expected_result = {'cpu': 'amd',
                       'machine': 'Windows-PC',
                       'os': 'linux',
                       'system': True}
    assert get_launch_sys_attrs() == expected_result


@mock.patch('reportportal_client.helpers.system', mock.Mock())
@mock.patch('reportportal_client.helpers.machine', mock.Mock())
@mock.patch('reportportal_client.helpers.processor',
            mock.Mock(return_value=''))
def test_get_launch_sys_attrs_docker():
    """Test that cpu key value is not empty.

    platform.processor() returns empty string in case it was called
    inside of the Docker container. API does not allow empty values
    for the attributes.
    """
    result = get_launch_sys_attrs()
    assert result['cpu'] == 'unknown'


@pytest.mark.parametrize(
    'attributes, expected_attributes',
    [
        ({'tn': 'v' * 129}, [{'key': 'tn', 'value': 'v' * (
                ATTRIBUTE_LENGTH_LIMIT - len(TRUNCATE_REPLACEMENT)) + TRUNCATE_REPLACEMENT}]),
        ({'tn': 'v' * 128}, [{'key': 'tn', 'value': 'v' * 128}]),
        ({'k' * 129: 'v'}, [{'key': 'k' * (
                ATTRIBUTE_LENGTH_LIMIT - len(TRUNCATE_REPLACEMENT)) + TRUNCATE_REPLACEMENT, 'value': 'v'}]),
        ({'k' * 128: 'v'}, [{'key': 'k' * 128, 'value': 'v'}]),
        ({'tn': 'v' * 128, 'system': True}, [{'key': 'tn', 'value': 'v' * 128, 'system': True}]),
        ({'tn': 'v' * 129, 'system': True}, [{'key': 'tn', 'value': 'v' * (
                ATTRIBUTE_LENGTH_LIMIT - len(TRUNCATE_REPLACEMENT)) + TRUNCATE_REPLACEMENT, 'system': True}]),
        ({'k' * 129: 'v', 'system': False}, [{'key': 'k' * (
                ATTRIBUTE_LENGTH_LIMIT - len(TRUNCATE_REPLACEMENT)) + TRUNCATE_REPLACEMENT, 'value': 'v',
                                              'system': False}]),
        ([{'key': 'tn', 'value': 'v' * 129}], [{'key': 'tn', 'value': 'v' * (
                ATTRIBUTE_LENGTH_LIMIT - len(TRUNCATE_REPLACEMENT)) + TRUNCATE_REPLACEMENT}]),
        ([{'key': 'k' * 129, 'value': 'v'}], [{'key': 'k' * (
                ATTRIBUTE_LENGTH_LIMIT - len(TRUNCATE_REPLACEMENT)) + TRUNCATE_REPLACEMENT, 'value': 'v'}]),

    ]
)
def test_verify_value_length(attributes, expected_attributes):
    """Test for validate verify_value_length() function."""
    result = verify_value_length(attributes)
    assert len(result) == len(expected_attributes)
    for i, element in enumerate(result):
        expected = expected_attributes[i]
        assert len(element) == len(expected)
        assert element.get('key') == expected.get('key')
        assert element.get('value') == expected.get('value')
        assert element.get('system') == expected.get('system')


@pytest.mark.parametrize(
    'file, expected_is_binary',
    [
        ('test_res/pug/lucky.jpg', True),
        ('test_res/pug/unlucky.jpg', True),
        ('test_res/files/image.png', True),
        ('test_res/files/demo.zip', True),
        ('test_res/files/test.jar', True),
        ('test_res/files/test.pdf', True),
        ('test_res/files/test.bin', True),
        ('test_res/files/simple.txt', False),
    ]
)
def test_binary_content_detection(file, expected_is_binary):
    """Test for validate binary content detection."""
    with open(file, 'rb') as f:
        content = f.read()
    assert is_binary(content) == expected_is_binary


@pytest.mark.parametrize(
    'file, expected_type',
    [
        ('test_res/pug/lucky.jpg', 'image/jpeg'),
        ('test_res/pug/unlucky.jpg', 'image/jpeg'),
        ('test_res/files/image.png', 'image/png'),
        ('test_res/files/demo.zip', 'application/zip'),
        ('test_res/files/test.jar', 'application/java-archive'),
        ('test_res/files/test.pdf', 'application/pdf'),
        ('test_res/files/test.bin', 'application/octet-stream'),
        ('test_res/files/simple.txt', 'text/plain'),
    ]
)
def test_binary_content_type_detection(file, expected_type):
    """Test for validate binary content type detection."""
    with open(file, 'rb') as f:
        content = f.read()
    assert guess_content_type_from_bytes(content) == expected_type
