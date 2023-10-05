"""This module contains unit tests for statistics used in the project."""

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

import re
import sys
from unittest import mock

# noinspection PyPackageRequirements
import pytest
from requests.exceptions import RequestException

# noinspection PyProtectedMember
from reportportal_client._internal.services.constants import ENDPOINT, CLIENT_INFO
# noinspection PyProtectedMember
from reportportal_client._internal.services.statistics import send_event, async_send_event

VERSION_VAR = '__version__'
EVENT_NAME = 'start_launch'
with open('setup.py') as f:
    EXPECTED_CL_VERSION = next(
        map(lambda l: re.sub(f'^\\s*{VERSION_VAR}\\s*=\\s*[\'"]([^\'"]+)[\'"]', '\\g<1>', l),
            filter(lambda x: VERSION_VAR in x, f.read().splitlines())))
EXPECTED_CL_NAME = 'reportportal-client'
AGENT_VERSION, AGENT_NAME = '5.0.5', 'pytest-reportportal'
EXPECTED_HEADERS = {'User-Agent': 'python-requests'}
EXPECTED_AIO_HEADERS = {'User-Agent': 'python-aiohttp'}
EXPECTED_DATA = {
    'client_id': '555',
    'events': [{
        'name': EVENT_NAME,
        'params': {
            'client_name': EXPECTED_CL_NAME,
            'client_version': EXPECTED_CL_VERSION,
            'interpreter': 'Python 3.6.6',
            'agent_name': AGENT_NAME,
            'agent_version': AGENT_VERSION,
        }
    }]
}
MID, KEY = CLIENT_INFO.split(':')
EXPECTED_PARAMS = {'measurement_id': MID, 'api_secret': KEY}


@mock.patch('reportportal_client.services.statistics.get_client_id',
            mock.Mock(return_value='555'))
@mock.patch('reportportal_client.services.statistics.requests.post')
@mock.patch('reportportal_client.services.statistics.python_version',
            mock.Mock(return_value='3.6.6'))
def test_send_event(mocked_requests):
    """Test functionality of the send_event() function.

    :param mocked_requests:     Mocked requests module
    """

    send_event(EVENT_NAME, AGENT_NAME, AGENT_VERSION)
    mocked_requests.assert_called_with(
        url=ENDPOINT, json=EXPECTED_DATA, headers=EXPECTED_HEADERS,
        params=EXPECTED_PARAMS)


@mock.patch('reportportal_client.services.statistics.get_client_id',
            mock.Mock(return_value='555'))
@mock.patch('reportportal_client.services.statistics.requests.post',
            mock.Mock(side_effect=RequestException))
def test_send_event_raises():
    """Test that the send_event() does not raise exceptions."""
    send_event(EVENT_NAME, 'pytest-reportportal', '5.0.5')


@mock.patch('reportportal_client.services.statistics.requests.post')
@mock.patch('reportportal_client.services.statistics.python_version',
            mock.Mock(return_value='3.6.6'))
def test_same_client_id(mocked_requests):
    """Test functionality of the send_event() function.

    :param mocked_requests:     Mocked requests module
    """
    agent_version, agent_name = '5.0.5', 'pytest-reportportal'

    send_event(EVENT_NAME, agent_name, agent_version)
    send_event(EVENT_NAME, agent_name, agent_version)
    args_list = mocked_requests.call_args_list

    result1 = args_list[0][1]['json']['client_id']
    result2 = args_list[1][1]['json']['client_id']

    assert result1 == result2


MOCKED_AIOHTTP = None
if not sys.version_info < (3, 8):
    MOCKED_AIOHTTP = mock.AsyncMock()


@pytest.mark.skipif(sys.version_info < (3, 8),
                    reason="the test requires AsyncMock which was introduced in Python 3.8")
@mock.patch('reportportal_client.services.statistics.get_client_id',
            mock.Mock(return_value='555'))
@mock.patch('reportportal_client.services.statistics.aiohttp.ClientSession.post', MOCKED_AIOHTTP)
@mock.patch('reportportal_client.services.statistics.python_version',
            mock.Mock(return_value='3.6.6'))
@pytest.mark.asyncio
async def test_async_send_event():
    """Test functionality of the send_event() function."""
    await async_send_event(EVENT_NAME, AGENT_NAME, AGENT_VERSION)
    assert len(MOCKED_AIOHTTP.call_args_list) == 1
    args, kwargs = MOCKED_AIOHTTP.call_args_list[0]
    assert len(args) == 0
    expected_kwargs_keys = ['headers', 'url', 'json', 'params', 'ssl']
    for key in expected_kwargs_keys:
        assert key in kwargs
    assert len(expected_kwargs_keys) == len(kwargs)
    assert kwargs['headers'] == EXPECTED_AIO_HEADERS
    assert kwargs['url'] == ENDPOINT
    assert kwargs['json'] == EXPECTED_DATA
    assert kwargs['params'] == EXPECTED_PARAMS
    assert kwargs['ssl'] is not None
