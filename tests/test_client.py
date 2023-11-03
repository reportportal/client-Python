#  Copyright (c) 2022 https://reportportal.io .
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
from io import StringIO
from unittest import mock

# noinspection PyPackageRequirements
import pytest
from requests import Response
from requests.exceptions import ReadTimeout

from reportportal_client import RPClient
from reportportal_client.core.rp_requests import RPRequestLog
from reportportal_client.helpers import timestamp


def connection_error(*args, **kwargs):
    raise ReadTimeout()


def response_error(*args, **kwargs):
    result = Response()
    result._content = '502 Gateway Timeout'.encode('ASCII')
    result.status_code = 502
    return result


def invalid_response(*args, **kwargs):
    result = Response()
    result._content = \
        '<html><head><title>Hello World!</title></head></html>'
    result.status_code = 200
    return result


@pytest.mark.parametrize(
    'requests_method, client_method, client_params',
    [
        ('put', 'finish_launch', [timestamp()]),
        ('put', 'finish_test_item', ['test_item_id', timestamp()]),
        ('get', 'get_item_id_by_uuid', ['test_item_uuid']),
        ('get', 'get_launch_info', []),
        ('get', 'get_launch_ui_id', []),
        ('get', 'get_launch_ui_url', []),
        ('get', 'get_project_settings', []),
        ('post', 'start_launch', ['Test Launch', timestamp()]),
        ('post', 'start_test_item', ['Test Item', timestamp(), 'STEP']),
        ('put', 'update_test_item', ['test_item_id'])
    ]
)
def test_connection_errors(rp_client, requests_method, client_method,
                           client_params):
    rp_client._RPClient__launch_uuid = 'test_launch_id'
    getattr(rp_client.session, requests_method).side_effect = connection_error
    result = getattr(rp_client, client_method)(*client_params)
    assert result is None

    getattr(rp_client.session, requests_method).side_effect = response_error
    result = getattr(rp_client, client_method)(*client_params)
    assert result is None

    getattr(rp_client.session, requests_method).side_effect = invalid_response
    result = getattr(rp_client, client_method)(*client_params)
    assert result is None


LAUNCH_ID = 333
EXPECTED_DEFAULT_URL = 'http://endpoint/ui/#project/launches/all/' + str(
    LAUNCH_ID)
EXPECTED_DEBUG_URL = 'http://endpoint/ui/#project/userdebug/all/' + str(
    LAUNCH_ID)


@pytest.mark.parametrize(
    'launch_mode, project_name, expected_url',
    [
        ('DEFAULT', "project", EXPECTED_DEFAULT_URL),
        ('DEBUG', "project", EXPECTED_DEBUG_URL),
        ('DEFAULT', "PROJECT", EXPECTED_DEFAULT_URL),
        ('debug', "PROJECT", EXPECTED_DEBUG_URL)
    ]
)
def test_launch_url_get(rp_client, launch_mode, project_name, expected_url):
    rp_client._RPClient__launch_uuid = 'test_launch_id'
    rp_client._RPClient__project = project_name

    response = mock.Mock()
    response.is_success = True
    response.json.side_effect = lambda: {'mode': launch_mode, 'id': LAUNCH_ID}

    def get_call(*args, **kwargs):
        return response

    rp_client.session.get.side_effect = get_call

    assert rp_client.get_launch_ui_url() == expected_url


@mock.patch('reportportal_client.client.getenv')
@mock.patch('reportportal_client.client.send_event')
def test_skip_statistics(send_event, getenv):
    getenv.return_value = '1'
    client = RPClient('http://endpoint', 'project', 'api_key')
    client.session = mock.Mock()
    client.start_launch('Test Launch', timestamp())
    assert mock.call('start_launch', None, None) not in send_event.mock_calls


@mock.patch('reportportal_client.client.getenv')
@mock.patch('reportportal_client.client.send_event')
def test_statistics(send_event, getenv):
    getenv.return_value = ''
    client = RPClient('http://endpoint', 'project', 'api_key')
    client.session = mock.Mock()
    client.start_launch('Test Launch', timestamp())
    assert mock.call('start_launch', None, None) in send_event.mock_calls


def test_clone():
    args = ['http://endpoint', 'project']
    kwargs = {'api_key': 'api_key', 'log_batch_size': 30,
              'is_skipped_an_issue': False, 'verify_ssl': False, 'retries': 5,
              'max_pool_size': 30, 'launch_id': 'test-123',
              'http_timeout': (30, 30),
              'log_batch_payload_size': 1000000, 'mode': 'DEBUG'}
    client = RPClient(*args, **kwargs)
    client._add_current_item('test-321')
    client._add_current_item('test-322')
    cloned = client.clone()
    assert cloned is not None and client is not cloned
    assert cloned.endpoint == args[0] and cloned.project == args[1]
    assert (
            cloned.api_key == kwargs['api_key']
            and cloned.log_batch_size == kwargs['log_batch_size']
            and cloned.is_skipped_an_issue == kwargs['is_skipped_an_issue']
            and cloned.verify_ssl == kwargs['verify_ssl']
            and cloned.retries == kwargs['retries']
            and cloned.max_pool_size == kwargs['max_pool_size']
            and cloned.launch_uuid == kwargs['launch_id']
            and cloned.launch_id == kwargs['launch_id']
            and cloned.http_timeout == kwargs['http_timeout']
            and cloned.log_batch_payload_size == kwargs['log_batch_payload_size']
            and cloned.mode == kwargs['mode']
    )
    assert cloned._item_stack.qsize() == 1 \
           and client.current_item() == cloned.current_item()


@mock.patch('reportportal_client.client.warnings.warn')
def test_deprecated_token_argument(warn):
    api_key = 'api_key'
    client = RPClient(endpoint='http://endpoint', project='project',
                      token=api_key)

    assert warn.call_count == 1
    assert client.api_key == api_key


@mock.patch('reportportal_client.client.warnings.warn')
def test_api_key_argument(warn):
    api_key = 'api_key'
    client = RPClient(endpoint='http://endpoint', project='project',
                      api_key=api_key)

    assert warn.call_count == 0
    assert client.api_key == api_key


@mock.patch('reportportal_client.client.warnings.warn')
def test_empty_api_key_argument(warn):
    api_key = ''
    client = RPClient(endpoint='http://endpoint', project='project',
                      api_key=api_key)

    assert warn.call_count == 1
    assert client.api_key == api_key


def test_launch_uuid_print():
    str_io = StringIO()
    output_mock = mock.Mock()
    output_mock.get_output.side_effect = lambda: str_io
    client = RPClient(endpoint='http://endpoint', project='project',
                      api_key='test', launch_uuid_print=True, print_output=output_mock)
    client.session = mock.Mock()
    client._skip_analytics = True
    client.start_launch('Test Launch', timestamp())
    assert 'ReportPortal Launch UUID: ' in str_io.getvalue()


def test_no_launch_uuid_print():
    str_io = StringIO()
    output_mock = mock.Mock()
    output_mock.get_output.side_effect = lambda: str_io
    client = RPClient(endpoint='http://endpoint', project='project',
                      api_key='test', launch_uuid_print=False, print_output=output_mock)
    client.session = mock.Mock()
    client._skip_analytics = True
    client.start_launch('Test Launch', timestamp())
    assert 'ReportPortal Launch UUID: ' not in str_io.getvalue()


@mock.patch('reportportal_client.client.sys.stdout', new_callable=StringIO)
def test_launch_uuid_print_default_io(mock_stdout):
    client = RPClient(endpoint='http://endpoint', project='project',
                      api_key='test', launch_uuid_print=True)
    client.session = mock.Mock()
    client._skip_analytics = True
    client.start_launch('Test Launch', timestamp())

    assert 'ReportPortal Launch UUID: ' in mock_stdout.getvalue()


@mock.patch('reportportal_client.client.sys.stdout', new_callable=StringIO)
def test_launch_uuid_print_default_print(mock_stdout):
    client = RPClient(endpoint='http://endpoint', project='project',
                      api_key='test')
    client.session = mock.Mock()
    client._skip_analytics = True
    client.start_launch('Test Launch', timestamp())

    assert 'ReportPortal Launch UUID: ' not in mock_stdout.getvalue()


def test_client_pickling():
    client = RPClient('http://localhost:8080', 'default_personal', api_key='test_key')
    pickled_client = pickle.dumps(client)
    unpickled_client = pickle.loads(pickled_client)
    assert unpickled_client is not None


@pytest.mark.parametrize(
    'method, call_method, arguments',
    [
        ('start_launch', 'post', ['Test Launch', timestamp()]),
        ('start_test_item', 'post', ['Test Item', timestamp(), 'SUITE']),
        ('finish_test_item', 'put', ['test_item_uuid', timestamp()]),
        ('finish_launch', 'put', [timestamp()]),
        ('update_test_item', 'put', ['test_item_uuid']),
    ]
)
def test_attribute_truncation(rp_client: RPClient, method, call_method, arguments):
    # noinspection PyTypeChecker
    session: mock.Mock = rp_client.session
    if method != 'start_launch':
        rp_client._RPClient__launch_uuid = 'test_launch_id'

    getattr(rp_client, method)(*arguments, **{'attributes': {'key': 'value' * 26}})
    getattr(session, call_method).assert_called_once()
    kwargs = getattr(session, call_method).call_args_list[0][1]
    assert 'attributes' in kwargs['json']
    assert kwargs['json']['attributes']
    assert len(kwargs['json']['attributes'][0]['value']) == 128


@pytest.mark.parametrize(
    'method, call_method, arguments',
    [
        ('start_launch', 'post', ['Test Launch', timestamp()]),
        ('start_test_item', 'post', ['Test Item', timestamp(), 'SUITE']),
        ('finish_test_item', 'put', ['test_item_uuid', timestamp()]),
        ('finish_launch', 'put', [timestamp()]),
        ('update_test_item', 'put', ['test_item_uuid']),
        ('get_launch_info', 'get', []),
        ('get_project_settings', 'get', []),
        ('get_item_id_by_uuid', 'get', ['test_item_uuid']),
        ('log', 'post', [timestamp(), 'Test Message']),
    ]
)
def test_http_timeout_bypass(method, call_method, arguments):
    http_timeout = (35.1, 33.3)
    rp_client = RPClient('http://endpoint', 'project', 'api_key',
                         http_timeout=http_timeout, log_batch_size=1)
    session: mock.Mock = mock.Mock()
    rp_client.session = session
    rp_client._skip_analytics = True

    if method != 'start_launch':
        rp_client._RPClient__launch_uuid = 'test_launch_id'

    getattr(rp_client, method)(*arguments)
    getattr(session, call_method).assert_called_once()
    kwargs = getattr(session, call_method).call_args_list[0][1]
    assert 'timeout' in kwargs
    assert kwargs['timeout'] == http_timeout


def test_logs_flush_on_close(rp_client: RPClient):
    # noinspection PyTypeChecker
    session: mock.Mock = rp_client.session
    batcher: mock.Mock = mock.Mock()
    batcher.flush.return_value = [RPRequestLog('test_launch_uuid', timestamp(), message='test_message')]
    rp_client._log_batcher = batcher

    rp_client.close()

    batcher.flush.assert_called_once()
    session.post.assert_called_once()
    session.close.assert_called_once()
