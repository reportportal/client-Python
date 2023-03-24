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
import os
from platform import python_version
from uuid import uuid4

import requests
from pkg_resources import get_distribution

from .constants import CLIENT_INFO, ENDPOINT, CLIENT_ID_PROPERTY

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


def _load_properties(filepath, sep='=', comment_char='#'):
    """
    Read the file passed as parameter as a properties file.
    """
    result = {}
    with open(filepath, "rt") as f:
        for line in f:
            s_line = line.strip()
            if s_line and not s_line.startswith(comment_char):
                sep_idx = s_line.index(sep)
                key = s_line[0:sep_idx]
                value = s_line[sep_idx + 1:]
                result[key.rstrip()] = value.lstrip()
    return result


def _get_client_id():
    """Get client ID.

    :return: str represents the client ID
    """
    rp_folder = os.path.expanduser('~/.rp')
    rp_properties = os.path.join(rp_folder, 'rp.properties')
    client_id = None
    if os.path.exists(rp_properties):
        config = _load_properties(rp_properties)
        client_id = config.get(CLIENT_ID_PROPERTY)
    if not client_id:
        if not os.path.exists(rp_folder):
            os.mkdir(rp_folder)
        client_id = str(uuid4())
        with open(rp_properties, 'a') as f:
            f.write('\n' + CLIENT_ID_PROPERTY + '=' + client_id + '\n')
    return client_id


def send_event(event_name, agent_name, agent_version):
    """Send an event to statistics service.

     Use client and agent versions with their names.

    :param event_name: Event name to be used
    :param agent_name: Name of the agent that uses the client
    :param agent_version: Version of the agent
    """
    client_name, client_version = _get_client_info()
    params = {
        'client_name': client_name,
        'client_version': client_version,
        'interpreter': _get_platform_info(),
        'agent_name': agent_name,
        'agent_version': agent_version,
    }

    if agent_name:
        params['agent_name'] = agent_name
    if agent_version:
        params['agent_version'] = agent_version

    payload = {
        'client_id': _get_client_id(),
        'events': [{
            'name': event_name,
            'params': params
        }]
    }
    headers = {'User-Agent': 'python-requests'}
    params = {
        'measurement_id': ID,
        'api_secret': KEY
    }
    try:
        return requests.post(url=ENDPOINT, json=payload, headers=headers,
                             params=params)
    except requests.exceptions.RequestException as err:
        logger.debug('Failed to send data to Statistics service: %s', str(err))
