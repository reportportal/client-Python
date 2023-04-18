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

from requests.exceptions import RequestException
# noinspection PyUnresolvedReferences
from six.moves import mock

from reportportal_client.services.constants import ENDPOINT, CLIENT_INFO
from reportportal_client.services.statistics import send_event

EVENT_NAME = 'start_launch'


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
    expected_cl_version, expected_cl_name = '5.0.4', 'reportportal-client'
    agent_version, agent_name = '5.0.5', 'pytest-reportportal'
    mocked_distribution.return_value.version = expected_cl_version
    mocked_distribution.return_value.project_name = expected_cl_name

    expected_headers = {'User-Agent': 'python-requests'}

    expected_data = {
        'client_id': '555',
        'events': [{
            'name': EVENT_NAME,
            'params': {
                'client_name': expected_cl_name,
                'client_version': expected_cl_version,
                'interpreter': 'Python 3.6.6',
                'agent_name': agent_name,
                'agent_version': agent_version,
            }
        }]
    }
    mid, key = CLIENT_INFO.split(':')
    expected_params = {'measurement_id': mid, 'api_secret': key}
    send_event(EVENT_NAME, agent_name, agent_version)
    mocked_requests.assert_called_with(
        url=ENDPOINT, json=expected_data, headers=expected_headers,
        params=expected_params)


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
