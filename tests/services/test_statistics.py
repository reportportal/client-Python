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

import sys
from unittest import mock

import pytest
from requests.exceptions import RequestException

from reportportal_client.services.constants import ENDPOINT, CLIENT_INFO
from reportportal_client.services.statistics import send_event, async_send_event

EVENT_NAME = 'start_launch'
EXPECTED_CL_VERSION, EXPECTED_CL_NAME = '5.0.4', 'reportportal-client'
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
@mock.patch('reportportal_client.services.statistics.get_distribution')
@mock.patch('reportportal_client.services.statistics.python_version',
            mock.Mock(return_value='3.6.6'))
def test_send_event(mocked_distribution, mocked_requests):
    """Test functionality of the send_event() function.

    :param mocked_distribution: Mocked get_distribution() function
    :param mocked_requests:     Mocked requests module
    """
    mocked_distribution.return_value.version = EXPECTED_CL_VERSION
    mocked_distribution.return_value.project_name = EXPECTED_CL_NAME

    send_event(EVENT_NAME, AGENT_NAME, AGENT_VERSION)
    mocked_requests.assert_called_with(
        url=ENDPOINT, json=EXPECTED_DATA, headers=EXPECTED_HEADERS,
        params=EXPECTED_PARAMS)


@mock.patch('reportportal_client.services.statistics.get_client_id',
            mock.Mock(return_value='555'))
@mock.patch('reportportal_client.services.statistics.requests.post',
            mock.Mock(side_effect=RequestException))
@mock.patch('reportportal_client.services.statistics.get_distribution',
            mock.Mock())
def test_send_event_raises():
    """Test that the send_event() does not raise exceptions."""
    send_event(EVENT_NAME, 'pytest-reportportal', '5.0.5')


@mock.patch('reportportal_client.services.statistics.requests.post')
@mock.patch('reportportal_client.services.statistics.get_distribution')
@mock.patch('reportportal_client.services.statistics.python_version',
            mock.Mock(return_value='3.6.6'))
def test_same_client_id(mocked_distribution, mocked_requests):
    """Test functionality of the send_event() function.

    :param mocked_distribution: Mocked get_distribution() function
    :param mocked_requests:     Mocked requests module
    """
    expected_cl_version, expected_cl_name = '5.0.4', 'reportportal-client'
    agent_version, agent_name = '5.0.5', 'pytest-reportportal'
    mocked_distribution.return_value.version = expected_cl_version
    mocked_distribution.return_value.project_name = expected_cl_name

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
@mock.patch('reportportal_client.services.statistics.get_distribution')
@mock.patch('reportportal_client.services.statistics.python_version',
            mock.Mock(return_value='3.6.6'))
@pytest.mark.asyncio
async def test_async_send_event(mocked_distribution):
    """Test functionality of the send_event() function.

    :param mocked_distribution: Mocked get_distribution() function
    """
    mocked_distribution.return_value.version = EXPECTED_CL_VERSION
    mocked_distribution.return_value.project_name = EXPECTED_CL_NAME

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
