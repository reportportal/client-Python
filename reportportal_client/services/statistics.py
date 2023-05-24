"""This module sends statistics events to a statistics service."""

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

import logging
from platform import python_version

import requests
from pkg_resources import get_distribution

from .client_id import get_client_id
from .constants import CLIENT_INFO, ENDPOINT

logger = logging.getLogger(__name__)

ID, KEY = CLIENT_INFO.split(':')


def _get_client_info():
    """Get name of the client and its version.

    :return: ('reportportal-client', '5.0.4')
    """
    client = get_distribution('reportportal-client')
    return client.project_name, client.version


def _get_platform_info():
    """Get current platform basic info, e.g.: 'Python 3.6.1'.

    :return: str represents the current platform, e.g.: 'Python 3.6.1'
    """
    return 'Python ' + python_version()


def send_event(event_name, agent_name, agent_version):
    """Send an event to statistics service.

     Use client and agent versions with their names.

    :param event_name: Event name to be used
    :param agent_name: Name of the agent that uses the client
    :param agent_version: Version of the agent
    """
    client_name, client_version = _get_client_info()
    request_params = {
        'client_name': client_name,
        'client_version': client_version,
        'interpreter': _get_platform_info(),
        'agent_name': agent_name,
        'agent_version': agent_version,
    }

    if agent_name:
        request_params['agent_name'] = agent_name
    if agent_version:
        request_params['agent_version'] = agent_version

    payload = {
        'client_id': get_client_id(),
        'events': [{
            'name': event_name,
            'params': request_params
        }]
    }
    headers = {'User-Agent': 'python-requests'}
    query_params = {
        'measurement_id': ID,
        'api_secret': KEY
    }
    try:
        return requests.post(url=ENDPOINT, json=payload, headers=headers,
                             params=query_params)
    except requests.exceptions.RequestException as err:
        logger.debug('Failed to send data to Statistics service: %s', str(err))
