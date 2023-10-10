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
import os
import pickle
import sys
from ssl import SSLContext
from typing import List
from unittest import mock

import aiohttp
# noinspection PyPackageRequirements
import pytest

from reportportal_client import OutputType
# noinspection PyProtectedMember
from reportportal_client._internal.aio.http import RetryingClientSession, DEFAULT_RETRY_NUMBER
# noinspection PyProtectedMember
from reportportal_client._internal.static.defines import NOT_SET
from reportportal_client.aio.client import Client

ENDPOINT = 'http://localhost:8080'
PROJECT = 'default_personal'
API_KEY = 'test_key'
RESPONSE_ID = 'test_launch_uuid'
RETURN_JSON = {'id': RESPONSE_ID}


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
@pytest.mark.asyncio
async def test_retries_param(retry_num, expected_class, expected_param):
    client = Client(ENDPOINT, PROJECT, api_key=API_KEY, retries=retry_num)
    session = await client.session()
    assert isinstance(session, expected_class)
    if expected_param is not NOT_SET:
        assert getattr(session, '_RetryingClientSession__retry_number') == expected_param


@pytest.mark.skipif(sys.version_info < (3, 8),
                    reason="For some reasons this does not work on Python 3.7 on Ubuntu, "
                           "but works on my Mac. Unfortunately GHA use Python 3.7 on Ubuntu.")
@pytest.mark.parametrize(
    'timeout_param, expected_connect_param, expected_sock_read_param',
    [
        ((15, 17), 15, 17),
        (21, 21, 21),
        (None, None, None)
    ]
)
@mock.patch('reportportal_client.aio.client.RetryingClientSession')
@pytest.mark.asyncio
async def test_timeout_param(mocked_session, timeout_param, expected_connect_param, expected_sock_read_param):
    client = Client(ENDPOINT, PROJECT, api_key=API_KEY, http_timeout=timeout_param)
    session = await client.session()
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


LAUNCH_ID = 333
EXPECTED_DEFAULT_URL = f'http://endpoint/ui/#project/launches/all/{LAUNCH_ID}'
EXPECTED_DEBUG_URL = f'http://endpoint/ui/#project/userdebug/all/{LAUNCH_ID}'


@pytest.mark.skipif(sys.version_info < (3, 8),
                    reason="the test requires AsyncMock which was introduced in Python 3.8")
@pytest.mark.parametrize(
    'launch_mode, project_name, expected_url',
    [
        ('DEFAULT', "project", EXPECTED_DEFAULT_URL),
        ('DEBUG', "project", EXPECTED_DEBUG_URL),
        ('DEFAULT', "PROJECT", EXPECTED_DEFAULT_URL),
        ('debug', "PROJECT", EXPECTED_DEBUG_URL)
    ]
)
@pytest.mark.asyncio
async def test_launch_url_get(aio_client, launch_mode: str, project_name: str, expected_url: str):
    aio_client.project = project_name
    response = mock.AsyncMock()
    response.is_success = True
    response.json.side_effect = lambda: {'mode': launch_mode, 'id': LAUNCH_ID}

    async def get_call(*args, **kwargs):
        return response

    (await aio_client.session()).get.side_effect = get_call

    assert await (aio_client.get_launch_ui_url('test_launch_uuid')) == expected_url


@pytest.mark.skipif(sys.version_info < (3, 8),
                    reason="For some reasons this does not work on Python 3.7 on Ubuntu, "
                           "but works on my Mac. Unfortunately GHA use Python 3.7 on Ubuntu.")
@pytest.mark.parametrize('default', [True, False])
@mock.patch('reportportal_client.aio.client.aiohttp.TCPConnector')
@pytest.mark.asyncio
async def test_verify_ssl_default(connector_mock: mock.Mock, default: bool):
    if default:
        client = Client('http://endpoint', 'project', api_key='api_key')
    else:
        client = Client('http://endpoint', 'project', api_key='api_key', verify_ssl=True)
    await client.session()
    connector_mock.assert_called_once()
    _, kwargs = connector_mock.call_args_list[0]
    ssl_context: SSLContext = kwargs.get('ssl', None)
    assert ssl_context is not None and isinstance(ssl_context, SSLContext)
    assert len(ssl_context.get_ca_certs()) > 0


@pytest.mark.skipif(sys.version_info < (3, 8),
                    reason="For some reasons this does not work on Python 3.7 on Ubuntu, "
                           "but works on my Mac. Unfortunately GHA use Python 3.7 on Ubuntu.")
@pytest.mark.parametrize('param_value', [False, None])
@mock.patch('reportportal_client.aio.client.aiohttp.TCPConnector')
@pytest.mark.asyncio
async def test_verify_ssl_off(connector_mock: mock.Mock, param_value):
    client = Client('http://endpoint', 'project', api_key='api_key', verify_ssl=param_value)
    await client.session()
    connector_mock.assert_called_once()
    _, kwargs = connector_mock.call_args_list[0]
    ssl_context: SSLContext = kwargs.get('ssl', None)
    assert ssl_context is not None and isinstance(ssl_context, bool) and not ssl_context


@pytest.mark.skipif(sys.version_info < (3, 8),
                    reason="For some reasons this does not work on Python 3.7 on Ubuntu, "
                           "but works on my Mac. Unfortunately GHA use Python 3.7 on Ubuntu.")
@mock.patch('reportportal_client.aio.client.aiohttp.TCPConnector')
@pytest.mark.asyncio
async def test_verify_ssl_str(connector_mock: mock.Mock):
    client = Client('http://endpoint', 'project', api_key='api_key',
                    verify_ssl=os.path.join(os.getcwd(), 'test_res/root.pem'))
    await client.session()
    connector_mock.assert_called_once()
    _, kwargs = connector_mock.call_args_list[0]
    ssl_context: SSLContext = kwargs.get('ssl', None)
    assert ssl_context is not None and isinstance(ssl_context, SSLContext)
    assert len(ssl_context.get_ca_certs()) == 1
    certificate = ssl_context.get_ca_certs()[0]
    assert certificate['subject'][1] == (('organizationName', 'Internet Security Research Group'),)
    assert certificate['notAfter'] == 'Jun  4 11:04:38 2035 GMT'


@pytest.mark.skipif(sys.version_info < (3, 8),
                    reason="For some reasons this does not work on Python 3.7 on Ubuntu, "
                           "but works on my Mac. Unfortunately GHA use Python 3.7 on Ubuntu.")
@mock.patch('reportportal_client.aio.client.aiohttp.TCPConnector')
@pytest.mark.asyncio
async def test_keepalive_timeout(connector_mock: mock.Mock):
    keepalive_timeout = 33
    client = Client('http://endpoint', 'project', api_key='api_key',
                    keepalive_timeout=keepalive_timeout)
    await client.session()
    connector_mock.assert_called_once()
    _, kwargs = connector_mock.call_args_list[0]
    timeout = kwargs.get('keepalive_timeout', None)
    assert timeout is not None and timeout == keepalive_timeout


@pytest.mark.skipif(sys.version_info < (3, 8),
                    reason="the test requires AsyncMock which was introduced in Python 3.8")
@pytest.mark.asyncio
async def test_close(aio_client: Client):
    # noinspection PyTypeChecker
    session: mock.AsyncMock = await aio_client.session()
    await (aio_client.close())
    assert aio_client._session is None
    session.close.assert_awaited_once()


def mock_basic_post_response(session):
    return_object = mock.AsyncMock()
    return_object.json.return_value = RETURN_JSON
    session.post.return_value = return_object


def verify_attributes(expected_attributes: dict, actual_attributes: List[dict]):
    if expected_attributes is None:
        assert actual_attributes is None
        return
    else:
        assert actual_attributes is not None
    assert len(actual_attributes) == len(expected_attributes.items())
    for attribute in actual_attributes:
        if 'key' in attribute:
            assert expected_attributes.get(attribute.get('key')) == attribute.get('value')
            assert attribute.get('system') is False


@pytest.mark.skipif(sys.version_info < (3, 8),
                    reason="the test requires AsyncMock which was introduced in Python 3.8")
@pytest.mark.asyncio
async def test_start_launch(aio_client: Client):
    # noinspection PyTypeChecker
    session: mock.AsyncMock = await aio_client.session()
    mock_basic_post_response(session)

    launch_name = 'Test Launch'
    start_time = str(1696921416000)
    description = 'Test Launch description'
    attributes = {'attribute_key': 'attribute_value'}
    rerun_of = 'test_prent_launch_uuid'
    result = await aio_client.start_launch(launch_name, start_time, description=description,
                                           attributes=attributes, rerun=True, rerun_of=rerun_of)

    assert result == RESPONSE_ID
    session.post.assert_called_once()
    call_args = session.post.call_args_list[0]
    assert '/api/v2/project/launch' == call_args[0][0]
    kwargs = call_args[1]
    assert kwargs.get('data') is None
    actual_json = kwargs.get('json')
    assert actual_json is not None
    assert actual_json.get('rerun') is True
    assert actual_json.get('rerunOf') == rerun_of
    assert actual_json.get('description') == description
    assert actual_json.get('startTime') == start_time
    actual_attributes = actual_json.get('attributes')
    verify_attributes(attributes, actual_attributes)


@pytest.mark.skipif(sys.version_info < (3, 8),
                    reason="the test requires AsyncMock which was introduced in Python 3.8")
@mock.patch('reportportal_client.aio.client.async_send_event')
@pytest.mark.asyncio
async def test_start_launch_event_send(async_send_event):
    # noinspection PyTypeChecker
    session = mock.AsyncMock()
    client = Client('http://endpoint', 'project', api_key='api_key')
    client._session = session
    mock_basic_post_response(session)

    launch_name = 'Test Launch'
    start_time = str(1696921416000)
    agent_name = 'pytest-reportportal'
    agent_version = '5.0.4'
    attributes = {'agent': f'{agent_name}|{agent_version}'}
    await client.start_launch(launch_name, start_time, attributes=attributes)
    async_send_event.assert_called_once()
    call_args = async_send_event.call_args_list[0]
    args = call_args[0]
    kwargs = call_args[1]
    assert len(args) == 3
    assert args[0] == 'start_launch'
    assert args[1] == agent_name
    assert args[2] == agent_version
    assert len(kwargs.items()) == 0
