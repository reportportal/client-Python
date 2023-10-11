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
from io import StringIO
from json import JSONDecodeError
from ssl import SSLContext
from typing import List
from unittest import mock

import aiohttp
# noinspection PyPackageRequirements
import pytest
from aiohttp import ServerConnectionError

from reportportal_client import OutputType
# noinspection PyProtectedMember
from reportportal_client._internal.aio.http import RetryingClientSession, DEFAULT_RETRY_NUMBER
# noinspection PyProtectedMember
from reportportal_client._internal.static.defines import NOT_SET
from reportportal_client.aio.client import Client
from reportportal_client.core.rp_issues import Issue
from reportportal_client.core.rp_requests import AsyncRPRequestLog
from reportportal_client.helpers import timestamp

ENDPOINT = 'http://localhost:8080'
PROJECT = 'default_personal'
API_KEY = 'test_key'
RESPONSE_ID = 'test_launch_uuid'
RETURN_POST_JSON = {'id': RESPONSE_ID}
RESPONSE_MESSAGE = 'Item finished successfully'
RETURN_PUT_JSON = {'message': RESPONSE_MESSAGE}


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
    return_object.json.return_value = RETURN_POST_JSON
    session.post.return_value = return_object


def verify_attributes(expected_attributes: dict, actual_attributes: List[dict]):
    if expected_attributes is None:
        assert actual_attributes is None
        return
    else:
        assert actual_attributes is not None
    assert len(actual_attributes) == len(expected_attributes)
    for attribute in actual_attributes:
        if 'key' in attribute:
            assert expected_attributes.get(attribute.get('key')) == attribute.get('value')
            assert attribute.get('system') is False


@pytest.mark.skipif(sys.version_info < (3, 8),
                    reason='the test requires AsyncMock which was introduced in Python 3.8')
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
                    reason='the test requires AsyncMock which was introduced in Python 3.8')
@mock.patch('reportportal_client.aio.client.async_send_event')
@pytest.mark.asyncio
async def test_start_launch_statistics_send(async_send_event):
    # noinspection PyTypeChecker
    session = mock.AsyncMock()
    client = Client('http://endpoint', 'project', api_key='api_key')
    client._skip_analytics = False
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


@pytest.mark.skipif(sys.version_info < (3, 8),
                    reason='the test requires AsyncMock which was introduced in Python 3.8')
@mock.patch('reportportal_client.aio.client.getenv')
@mock.patch('reportportal_client.aio.client.async_send_event')
@pytest.mark.asyncio
async def test_start_launch_no_statistics_send(async_send_event, getenv):
    getenv.return_value = '1'
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
    async_send_event.assert_not_called()


@pytest.mark.skipif(sys.version_info < (3, 8),
                    reason="the test requires AsyncMock which was introduced in Python 3.8")
@pytest.mark.asyncio
async def test_launch_uuid_print():
    str_io = StringIO()
    output_mock = mock.Mock()
    output_mock.get_output.return_value = str_io
    client = Client(endpoint='http://endpoint', project='project',
                    api_key='test', launch_uuid_print=True, print_output=output_mock)
    client._session = mock.AsyncMock()
    client._skip_analytics = True
    await client.start_launch('Test Launch', timestamp())
    assert 'ReportPortal Launch UUID: ' in str_io.getvalue()


@pytest.mark.skipif(sys.version_info < (3, 8),
                    reason="the test requires AsyncMock which was introduced in Python 3.8")
@pytest.mark.asyncio
async def test_no_launch_uuid_print():
    str_io = StringIO()
    output_mock = mock.Mock()
    output_mock.get_output.return_value = str_io
    client = Client(endpoint='http://endpoint', project='project',
                    api_key='test', launch_uuid_print=False, print_output=output_mock)
    client._session = mock.AsyncMock()
    client._skip_analytics = True
    await client.start_launch('Test Launch', timestamp())
    assert 'ReportPortal Launch UUID: ' not in str_io.getvalue()


@pytest.mark.skipif(sys.version_info < (3, 8),
                    reason="the test requires AsyncMock which was introduced in Python 3.8")
@pytest.mark.asyncio
@mock.patch('reportportal_client.client.sys.stdout', new_callable=StringIO)
async def test_launch_uuid_print_default_io(mock_stdout):
    client = Client(endpoint='http://endpoint', project='project',
                    api_key='test', launch_uuid_print=True)
    client._session = mock.AsyncMock()
    client._skip_analytics = True
    await client.start_launch('Test Launch', timestamp())
    assert 'ReportPortal Launch UUID: ' in mock_stdout.getvalue()


@pytest.mark.skipif(sys.version_info < (3, 8),
                    reason="the test requires AsyncMock which was introduced in Python 3.8")
@pytest.mark.asyncio
@mock.patch('reportportal_client.client.sys.stdout', new_callable=StringIO)
async def test_launch_uuid_print_default_print(mock_stdout):
    client = Client(endpoint='http://endpoint', project='project',
                    api_key='test')
    client._session = mock.AsyncMock()
    client._skip_analytics = True
    await client.start_launch('Test Launch', timestamp())
    assert 'ReportPortal Launch UUID: ' not in mock_stdout.getvalue()


def connection_error(*args, **kwargs):
    raise ServerConnectionError()


def json_error(*args, **kwargs):
    raise JSONDecodeError('invalid Json', '502 Gateway Timeout', 0)


def response_error(*args, **kwargs):
    result = mock.AsyncMock()
    result.ok = False
    result.json.side_effect = json_error
    result.status_code = 502
    return result


def invalid_response(*args, **kwargs):
    result = mock.AsyncMock()
    result.ok = True
    result.json.side_effect = json_error
    result.status_code = 200
    return result


@pytest.mark.skipif(sys.version_info < (3, 8),
                    reason="the test requires AsyncMock which was introduced in Python 3.8")
@pytest.mark.parametrize(
    'requests_method, client_method, client_params',
    [
        ('post', 'start_launch', ['Test Launch', timestamp()]),
        ('put', 'finish_launch', ['launch_uuid', timestamp()]),
        ('post', 'start_test_item', ['launch_uuid', 'Test Item', timestamp(), 'STEP']),
        ('put', 'finish_test_item', ['launch_uuid', 'test_item_id', timestamp()]),
        ('put', 'update_test_item', ['test_item_id']),
        ('get', 'get_item_id_by_uuid', ['test_item_uuid']),
        ('get', 'get_launch_info', ['launch_uuid']),
        ('get', 'get_launch_ui_id', ['launch_uuid']),
        ('get', 'get_launch_ui_url', ['launch_uuid']),
        ('get', 'get_project_settings', []),
        ('post', 'log_batch', [[AsyncRPRequestLog('launch_uuid', timestamp(), item_uuid='test_item_uuid')]])
    ]
)
@pytest.mark.asyncio
async def test_connection_errors(aio_client, requests_method, client_method,
                                 client_params):
    getattr(await aio_client.session(), requests_method).side_effect = connection_error
    try:
        await getattr(aio_client, client_method)(*client_params)
    except Exception as e:
        # On this level we pass all errors through by design
        assert type(e) == ServerConnectionError

    getattr(await aio_client.session(), requests_method).side_effect = response_error
    result = await getattr(aio_client, client_method)(*client_params)
    assert result is None

    getattr(await aio_client.session(), requests_method).side_effect = invalid_response
    result = await getattr(aio_client, client_method)(*client_params)
    assert result is None


def verify_parameters(expected_parameters: dict, actual_parameters: List[dict]):
    if expected_parameters is None:
        assert actual_parameters is None
        return
    else:
        assert actual_parameters is not None
    assert len(actual_parameters) == len(expected_parameters)
    for attribute in actual_parameters:
        assert expected_parameters.get(attribute.get('key')) == attribute.get('value')


@pytest.mark.skipif(sys.version_info < (3, 8),
                    reason='the test requires AsyncMock which was introduced in Python 3.8')
@pytest.mark.parametrize(
    'parent_id, expected_uri',
    [
        ('test_parent_uuid', '/api/v2/project/item/test_parent_uuid'),
        (None, '/api/v2/project/item'),
    ]
)
@pytest.mark.asyncio
async def test_start_test_item(aio_client: Client, parent_id, expected_uri):
    # noinspection PyTypeChecker
    session: mock.AsyncMock = await aio_client.session()
    mock_basic_post_response(session)

    launch_uuid = 'test_launch_uuid'
    item_name = 'Test Item'
    start_time = str(1696921416000)
    item_type = 'STEP'
    description = 'Test Launch description'
    attributes = {'attribute_key': 'attribute_value'}
    parameters = {'parameter_key': 'parameter_value'}
    code_ref = 'io.reportportal.test'
    test_case_id = 'io.reportportal.test[parameter_value]'
    result = await aio_client.start_test_item(launch_uuid, item_name, start_time, item_type,
                                              parent_item_id=parent_id, description=description,
                                              attributes=attributes, parameters=parameters,
                                              has_stats=False, code_ref=code_ref, test_case_id=test_case_id,
                                              retry=True)

    assert result == RESPONSE_ID
    session.post.assert_called_once()
    call_args = session.post.call_args_list[0]
    assert expected_uri == call_args[0][0]
    kwargs = call_args[1]
    assert kwargs.get('data') is None
    actual_json = kwargs.get('json')
    assert actual_json is not None
    assert actual_json.get('retry') is True
    assert actual_json.get('testCaseId') == test_case_id
    assert actual_json.get('codeRef') == code_ref
    assert actual_json.get('hasStats') is False
    assert actual_json.get('description') == description
    assert actual_json.get('parentId') is None
    assert actual_json.get('type') == item_type
    assert actual_json.get('startTime') == start_time
    assert actual_json.get('name') == item_name
    assert actual_json.get('launchUuid') == launch_uuid
    actual_attributes = actual_json.get('attributes')
    verify_attributes(attributes, actual_attributes)
    actual_parameters = actual_json.get('parameters')
    verify_parameters(parameters, actual_parameters)


@pytest.mark.skipif(sys.version_info < (3, 8),
                    reason='the test requires AsyncMock which was introduced in Python 3.8')
@pytest.mark.asyncio
async def test_start_test_item_default_values(aio_client: Client):
    # noinspection PyTypeChecker
    session: mock.AsyncMock = await aio_client.session()
    mock_basic_post_response(session)

    expected_uri = '/api/v2/project/item'
    launch_uuid = 'test_launch_uuid'
    item_name = 'Test Item'
    start_time = str(1696921416000)
    item_type = 'STEP'
    result = await aio_client.start_test_item(launch_uuid, item_name, start_time, item_type)

    assert result == RESPONSE_ID
    session.post.assert_called_once()
    call_args = session.post.call_args_list[0]
    assert expected_uri == call_args[0][0]
    kwargs = call_args[1]
    assert kwargs.get('data') is None
    actual_json = kwargs.get('json')
    assert actual_json is not None
    assert actual_json.get('retry') is False
    assert actual_json.get('testCaseId') is None
    assert actual_json.get('codeRef') is None
    assert actual_json.get('hasStats') is True
    assert actual_json.get('description') is None
    assert actual_json.get('parentId') is None
    assert actual_json.get('type') == item_type
    assert actual_json.get('startTime') == start_time
    assert actual_json.get('name') == item_name
    assert actual_json.get('launchUuid') == launch_uuid
    assert actual_json.get('attributes') is None
    assert actual_json.get('parameters') is None


def mock_basic_put_response(session):
    return_object = mock.AsyncMock()
    return_object.json.return_value = RETURN_PUT_JSON
    session.put.return_value = return_object


@pytest.mark.skipif(sys.version_info < (3, 8),
                    reason='the test requires AsyncMock which was introduced in Python 3.8')
@pytest.mark.asyncio
async def test_finish_test_item(aio_client: Client):
    # noinspection PyTypeChecker
    session: mock.AsyncMock = await aio_client.session()
    mock_basic_put_response(session)

    launch_uuid = 'test_launch_uuid'
    item_id = 'test_item_uuid'
    expected_uri = f'/api/v2/project/item/{item_id}'
    end_time = str(1696921416000)
    status = 'FAILED'
    description = 'Test Launch description'
    attributes = {'attribute_key': 'attribute_value'}
    issue = Issue('pb001', comment='Horrible bug!')

    result = await aio_client.finish_test_item(launch_uuid, item_id, end_time, status=status,
                                               description=description, attributes=attributes,
                                               issue=issue, retry=True)
    assert result == RESPONSE_MESSAGE
    session.put.assert_called_once()
    call_args = session.put.call_args_list[0]
    assert expected_uri == call_args[0][0]
    kwargs = call_args[1]
    assert kwargs.get('data') is None
    actual_json = kwargs.get('json')
    assert actual_json is not None
    assert actual_json.get('retry') is True
    assert actual_json.get('description') == description
    assert actual_json.get('launchUuid') == launch_uuid
    assert actual_json.get('endTime') == end_time
    assert actual_json.get('status') == status
    actual_attributes = actual_json.get('attributes')
    verify_attributes(attributes, actual_attributes)
    actual_issue = actual_json.get('issue')
    expected_issue = issue.payload
    assert len(actual_issue) == len(expected_issue)
    for entry in actual_issue.items():
        assert entry[1] == expected_issue[entry[0]]


@pytest.mark.skipif(sys.version_info < (3, 8),
                    reason='the test requires AsyncMock which was introduced in Python 3.8')
@pytest.mark.asyncio
async def test_finish_test_item_default_values(aio_client: Client):
    # noinspection PyTypeChecker
    session: mock.AsyncMock = await aio_client.session()
    mock_basic_put_response(session)

    launch_uuid = 'test_launch_uuid'
    item_id = 'test_item_uuid'
    expected_uri = f'/api/v2/project/item/{item_id}'
    end_time = str(1696921416000)

    result = await aio_client.finish_test_item(launch_uuid, item_id, end_time)
    assert result == RESPONSE_MESSAGE
    session.put.assert_called_once()
    call_args = session.put.call_args_list[0]
    assert expected_uri == call_args[0][0]
    kwargs = call_args[1]
    assert kwargs.get('data') is None
    actual_json = kwargs.get('json')
    assert actual_json is not None
    assert actual_json.get('retry') is False
    assert actual_json.get('description') is None
    assert actual_json.get('launchUuid') == launch_uuid
    assert actual_json.get('endTime') == end_time
    assert actual_json.get('status') is None
    assert actual_json.get('attributes') is None
    assert actual_json.get('issue') is None
