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

import pytest
from requests import Response
from requests.exceptions import ReadTimeout
from six.moves import mock

from reportportal_client.helpers import timestamp
from reportportal_client import RPClient


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
        '<html><head><title>405 Not Allowed</title></head></html>'
    result.status_code = 405
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
    rp_client.launch_id = 'test_launch_id'
    getattr(rp_client.session, requests_method).side_effect = connection_error
    result = getattr(rp_client, client_method)(*client_params)
    assert result is None

    getattr(rp_client.session, requests_method).side_effect = response_error
    result = getattr(rp_client, client_method)(*client_params)
    assert result is None


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
def test_invalid_responses(rp_client, requests_method, client_method,
                           client_params):
    rp_client.launch_id = 'test_launch_id'
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
    rp_client.launch_id = 'test_launch_id'
    rp_client.project = project_name

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
    client = RPClient('http://endpoint', 'project', 'token')
    client.session = mock.Mock()
    client.start_launch('Test Launch', timestamp())
    assert mock.call('start_launch', None, None) not in send_event.mock_calls


@mock.patch('reportportal_client.client.getenv')
@mock.patch('reportportal_client.client.send_event')
def test_statistics(send_event, getenv):
    getenv.return_value = ''
    client = RPClient('http://endpoint', 'project', 'token')
    client.session = mock.Mock()
    client.start_launch('Test Launch', timestamp())
    assert mock.call('start_launch', None, None) in send_event.mock_calls


def test_clone():
    args = ['http://endpoint', 'project', 'token']
    kwargs = {'log_batch_size': 30, 'is_skipped_an_issue': False,
              'verify_ssl': False, 'retries': 5,
              'max_pool_size': 30, 'launch_id': 'test-123',
              'http_timeout': (30, 30),
              'log_batch_payload_size': 1000000, 'mode': 'DEBUG'}
    client = RPClient(*args, **kwargs)
    client._item_stack.append('test-321')
    client._item_stack.append('test-322')
    cloned = client.clone()
    assert cloned is not None and client is not cloned
    assert cloned.endpoint == args[0] and cloned.project == args[
        1] and cloned.token == args[2]
    assert cloned.log_batch_size == kwargs[
        'log_batch_size'] and cloned.is_skipped_an_issue == kwargs[
               'is_skipped_an_issue'] and cloned.verify_ssl == kwargs[
               'verify_ssl'] and cloned.retries == kwargs[
               'retries'] and cloned.max_pool_size == kwargs[
               'max_pool_size'] and cloned.launch_id == kwargs[
               'launch_id'] and cloned.http_timeout == kwargs[
               'http_timeout'] and cloned.log_batch_payload_size == kwargs[
               'log_batch_payload_size'] and cloned.mode == kwargs['mode']
    assert len(cloned._item_stack) == 1 \
           and client.current_item() == cloned.current_item()
