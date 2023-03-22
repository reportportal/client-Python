import logging
from configparser import ConfigParser
from platform import python_version
from pkg_resources import get_distribution
import requests
import os
import json
import uuid

from .constants import CLIENT_INFO, ENDPOINT, EVENT_NAME, CLIENT_ID_PROPERTY

logger = logging.getLogger(__name__)

MEASUREMENT_ID, API_SECRET = CLIENT_INFO.split(':')


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


def _get_client_id():
    """Get client ID.

    :return: str represents the client ID
    """
    rp_folder = os.path.expanduser('~/.rp')
    rp_properties = os.path.join(rp_folder, 'rp.properties')
    client_id = None
    if os.path.exists(rp_properties):
        config = ConfigParser.RawConfigParser()
        config.read(rp_properties)
        client_id = str(config.get(CLIENT_ID_PROPERTY)).strip()
    if not client_id:
        if not os.path.exists(rp_folder):
            os.mkdir(rp_folder)
        client_id = str(uuid.uuid4())
        with open(rp_properties, 'a') as f:
            f.write('\n' + CLIENT_ID_PROPERTY + '=' + client_id + '\n')
    return client_id


def send_event(agent_name, agent_version):
    """Send an event to statistics service about client and agent versions with their names.

    :param agent_name: Name of the agent that uses the client
    :param agent_version: Version of the agent
    """
    client_name, client_version = _get_client_info()
    payload = {
        'client_id': _get_client_id(),
        'events': [{
            'name': EVENT_NAME,
            'params': {
                'client_name': client_name,
                'client_version': client_version,
                'interpreter': _get_platform_info(),
                'agent_name': agent_name,
                'agent_version': agent_version,
            }
        }]
    }
    headers = {'User-Agent': 'python-requests'}
    params = {
        'measurement_id': MEASUREMENT_ID,
        'api_secret': API_SECRET
    }
    try:
        return requests.post(url=ENDPOINT, data=json.dumps(payload), headers=headers, params=params)
    except requests.exceptions.RequestException as err:
        logger.debug('Failed to send data to Statistics service: %s', str(err))
