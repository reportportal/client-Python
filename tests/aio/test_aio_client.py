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

import pickle
from unittest import mock

import aiohttp
import pytest

from reportportal_client import OutputType
from reportportal_client.aio.client import Client
from reportportal_client.aio.http import RetryingClientSession, DEFAULT_RETRY_NUMBER
from reportportal_client.static.defines import NOT_SET

ENDPOINT = 'http://localhost:8080'
PROJECT = 'default_personal'
API_KEY = 'test_key'


def test_client_pickling():
    client = Client(ENDPOINT, PROJECT, api_key=API_KEY)
    pickled_client = pickle.dumps(client)
    unpickled_client = pickle.loads(pickled_client)
    assert unpickled_client is not None


@pytest.mark.parametrize(
    'retry_num, expected_class, expected_param',
    [
        (1, RetryingClientSession, 1),
        (0, aiohttp.ClientSession, NOT_SET),
        (-1, aiohttp.ClientSession, NOT_SET),
        (None, aiohttp.ClientSession, NOT_SET),
        (NOT_SET, RetryingClientSession, DEFAULT_RETRY_NUMBER)
    ]
)
def test_retries_param(retry_num, expected_class, expected_param):
    client = Client(ENDPOINT, PROJECT, api_key=API_KEY, retries=retry_num)
    session = client.session
    assert isinstance(session, expected_class)
    if expected_param is not NOT_SET:
        assert getattr(session, '_RetryingClientSession__retry_number') == expected_param


@pytest.mark.parametrize(
    'timeout_param, expected_connect_param, expected_sock_read_param',
    [
        ((15, 17), 15, 17),
        (21, 21, 21),
        (None, None, None)
    ]
)
@mock.patch('reportportal_client.aio.client.RetryingClientSession')
def test_timeout_param(mocked_session, timeout_param, expected_connect_param, expected_sock_read_param):
    client = Client(ENDPOINT, PROJECT, api_key=API_KEY, http_timeout=timeout_param)
    session = client.session
    assert session is not None
    assert len(mocked_session.call_args_list) == 1
    args, kwargs = mocked_session.call_args_list[0]
    assert len(args) == 1 and args[0] == ENDPOINT
    expected_kwargs_keys = ['headers', 'connector']
    if timeout_param:
        expected_kwargs_keys.append('timeout')
    for key in expected_kwargs_keys:
        assert key in kwargs
    assert len(expected_kwargs_keys) == len(kwargs)
    assert kwargs['headers'] == {'Authorization': f'Bearer {API_KEY}'}
    assert kwargs['connector'] is not None
    if timeout_param:
        assert kwargs['timeout'] is not None
        assert isinstance(kwargs['timeout'], aiohttp.ClientTimeout)
        assert kwargs['timeout'].connect == expected_connect_param
        assert kwargs['timeout'].sock_read == expected_sock_read_param


def test_clone():
    args = ['http://endpoint', 'project']
    kwargs = {'api_key': 'api_key', 'is_skipped_an_issue': False, 'verify_ssl': False, 'retries': 5,
              'max_pool_size': 30, 'http_timeout': (30, 30), 'keepalive_timeout': 25, 'mode': 'DEBUG',
              'launch_uuid_print': True, 'print_output': OutputType.STDERR}
    client = Client(*args, **kwargs)
    cloned = client.clone()
    assert cloned is not None and client is not cloned
    assert cloned.endpoint == args[0] and cloned.project == args[1]
    assert (
            cloned.api_key == kwargs['api_key']
            and cloned.is_skipped_an_issue == kwargs['is_skipped_an_issue']
            and cloned.verify_ssl == kwargs['verify_ssl']
            and cloned.retries == kwargs['retries']
            and cloned.max_pool_size == kwargs['max_pool_size']
            and cloned.http_timeout == kwargs['http_timeout']
            and cloned.keepalive_timeout == kwargs['keepalive_timeout']
            and cloned.mode == kwargs['mode']
            and cloned.launch_uuid_print == kwargs['launch_uuid_print']
            and cloned.print_output == kwargs['print_output']
    )
