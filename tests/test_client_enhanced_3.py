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
import warnings
from unittest import mock

from delayed_assert import expect, assert_expectations
from reportportal_client.aio.client import (Client, AsyncRPClient,
                                            BatchedRPClient, ThreadedRPClient)
from reportportal_client.client import RPClient
from reportportal_client.core.rp_issues import Issue
from reportportal_client.errors import RPInvalidStepUsage, RetentionError
from reportportal_client.steps import step

TEST_LAUNCH_ID = 'test_launch'


@mock.patch('reportportal_client.aio.client.requests.Session')
def test_client_init_verify_ignore_connectivity_true(mock_session):
    client = Client('http://endpoint', 'project', 'api_key',
                    verify_ssl=False, ignore_connectivity=True)
    expect(lambda: assert_that(client.session, has_properties({'verify': False})))
    expect(ending_with('.certifi')).empty(mock_session.call_args_list)


@mock.patch('reportportal_client.aio.client.requests.Session')
def test_client_init_verify_ignore_connectivity_false(mock_session):
    client = Client('http://endpoint', 'project', 'api_key',
                    verify_ssl=False, ignore_connectivity=False)
    expect(contains('[DEFAULT]\ndisable_warnings = True\nverify_ssl = False')).one_of(
            map(ending_with, map(str, mock_session.call_args_list)))


@mock.patch('reportportal_client.aio.client.requests.Session')
def test_client_init_verify_path(mock_session):
    client = Client('http://endpoint', 'project', 'api_key',
                    verify_ssl='/path/to/certificate.pem')
    expect(lambda: assert_that(client.session, has_properties({'verify': '/path/to/certificate.pem'})))
    expect(ending_with('.certificate.pem')).empty(mock_session.call_args_list)


@mock.patch('reportportal_client.aio.client.requests.Session')
def test_client_init_verify_ssl_default(mock_session):
    client = Client('http://endpoint', 'project', 'api_key')
    expect(lambda: assert_that(client.session, has_properties({'verify': True})))
    expect(empty(mock_session.call_args_list))


@mock.patch('reportportal_client.aio.client.requests.Session')
def test_client_init_use_insecure(mock_session):
    client = Client('http://endpoint', 'project', 'api_key', use_insecure=True)
    expect(lambda: assert_that(client.session, has_properties({'verify': False})))
    expect(ending_with('.certifi')).empty(mock_session.call_args_list)


@mock.patch('reportportal_client.aio.client.requests.Session')
def test_client_init_proxy(mock_session):
    cp = mock.create_default()
    cp.proxies = {'https': 'myproxy.com:8080'}

    client = Client('http://endpoint', 'project', 'api_key', verify_ssl=False, http_timeout=10)
    expect(lambda: assert_that(cp, has_properties(
        {
            'proxies': {'https': 'myproxy.com:8080'},
            'timeout': 10
        }
    )))
    expect(one_of(map(ending_with, map(str, mock_session.call_args_list))))


@mock.patch('reportportal_client.aio.client.requests.Session')
def test_client_init_no_proxy(mock_session):
    cp = mock.create_default()
    cp.proxies = {}

    client = Client('http://endpoint', 'project', 'api_key', verify_ssl=False, http_timeout=10)
    expect(lambda: assert_that(cp, has_properties(
        {
            'proxies': {},
            'timeout': 10
        }
    )))
    expect(one_of(map(ending_with, map(str, mock_session.call_args_list))))


@mock.patch('reportportal_client.aio.client.requests.Session')
def test_rp_client_init_basic_auth(mock_session):
    mock_session.return_value.headers.get.side_effect = [None, 'Authorization']
    client = RPClient(endpoint='http://endpoint', project='default_personal',
                      endpoint='http://endpoint', api_key='test_api_key')

    expect(lambda: assert_that(client.session.headers, has_key('Authorization')))


@mock.patch('reportportal_client.aio.client.requests.Session')
def test_rp_client_init_token_init_basic_auth(mock_session):
    mock_session.return_value.headers.get.side_effect = [None, None, None]
    client = RPClient(endpoint='http://endpoint', project='default_personal',
                      endpoint='http://endpoint', token='test_token')
    expect(lambda: assert_that(client.session.headers, has_key('Authorization')))


@mock.patch('reportportal_client.aio.client.requests.Session')
def test_rp_client_init_api_key_init_basic_auth(mock_session):
    mock_session.return_value.headers.get.side_effect = [None, None, None]
    client = RPClient(endpoint='http://endpoint', project='default_personal',
                      endpoint='http://endpoint', api_key='test_api_key')
    expect(lambda: assert_that(client.session.headers, has_key('Authorization')))


@mock.patch('reportportal_client.aio.client.requests.Session')
def test_rp_client_init_no_authentication(self, mock_session):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        client = RPClient(endpoint='http://endpoint', project='default_personal',
                          endpoint='http://endpoint')
        expect(lambda: assert_that(client.session.headers, has_no_key('Authorization')))


@mock.patch('reportportal_client.aio.client.requests.Session')
def test_rp_client_start_launch(self, mock_session):
    mock_start_launch = mock_session().post
    mock_start_launch.return_value =\
        mock.Mock(json=lambda: {"id": TEST_LAUNCH_ID}, status_code=200)

    client = RPClient(endpoint='http://endpoint', project='default_personal',
                      api_key='test_api_key')
    client.client = mock_session()

    rp = client.start_launch(name='Pytest', start_time='123', description='some_desc')
    expect(lambda: assert_that(rp, equal_to(TEST_LAUNCH_ID)))
    expect(lambda: assert_that(mock_start_launch.call_count, equal_to(1)))
    expect(lambda: assert_that(mock_start_launch.call_args[1]['files'], has_length(0)))

    client.start_launch(name='Pytest', start_time='123', description='some_desc',
                        files=['path/to/reportportal_client.html'])
    expect(that_items_are_unique(mock_start_launch.call_args_list))


@mock.patch('reportportal_client.aio.client.requests.Session')
def test_rp_client_start(self, mock_session):
    mock_start = mock_session().post
    mock_start.side_effects = [
        lambda *args, **kwargs: mock.Mock(
            json=lambda: {"id": "mock_session_id"},
            status_code=200,
        ),
        lambda *args, **kwargs: mock.Mock(
            json=lambda: {"item_id": "mock_item_id"}, status_code=200
        ),
    ]

    client = RPClient('http://endpoint', 'default_personal', api_key='test_api_key',
                      project='default_personal')
    client.client = mock_session()

    rp = step('old_school', lambda: None)
    expect(lambda: assert_that(rp, is_none()))
    expect(lambda: assert_that(mock_start.call_count, equal_to(2)))
    expect(lambda: assert_that(mock_start.call_args_list[0][1]['json']['name'], equal_to('root')))
    expect(lambda: assert_that(mock_start.call_args_list[1][1]['name'], equal_to('old_school')))


@mock.patch('reportportal_client.aio.client.requests.Session')
def test_rp_client_start_with_attributes(self, mock_session):
    mock_start = mock_session().post
    mock_start.side_effects = [
        lambda *args, **kwargs: mock.Mock(
            json=lambda: {"id": "mock_session_id"},
            status_code=200,
        ),
        lambda *args, **kwargs: mock.Mock(
            json=lambda: {"item_id": "mock_item_id"},
            status_code=200,
        ),
    ]

    client = RPClient('http://endpoint', 'default_personal', api_key='test_api_key',
                      project='default_personal')
    client.client = mock_session()

    rp = step(['severity:error'], lambda: None)
    expect(lambda: assert_that(rp, is_none()))
    expect(lambda: assert_that(mock_start.call_count, equal_to(2)))
    expect(lambda: assert_that(mock_start.call_args_list[1][1]['attributes'],
                               equal_to({'key': 'severity', 'value': 'error'})))


@mock.patch('reportportal_client.aio.client.requests.Session')
def test_rp_client_start_with_long_attributes(self, mock_session):
    rp_truncation_msg = 'Attribute values cannot exceed 128 characters in length. Value got: veryverylongattributevalue'
    mock_start = mock_session().post
    mock_start.side_effects = [
        lambda *args, **kwargs: mock.Mock(
            json=lambda: {"id": "mock_session_id"},
            status_code=200,
        ),
        lambda *args, **kwargs: mock.Mock(
            json=lambda: {"item_id": "mock_item_id"},
            status_code=200,
        ),
    ]

    client = RPClient('http://endpoint', 'default_personal', api_key='test_api_key',
                      project='default_personal')
    client.client = mock_session()

    with warning_handler(RPTruncationWarning) as wh:
        rp = step([('veryverylongattributename', 'veryverylongattributevalue')], lambda: None)
        expect(lambda: assert_that(rp, is_none()))
        expect(lambda: assert_that(mock_start.call_count, equal_to(2)))
        expect(lambda: assert_that(len(wh.warnings), equal_to(1)))
        expect(lambda: assert_that(str(wh.warnings[0]).startswith(rp_truncation_msg)))


@mock.patch('reportportal_client.aio.client.requests.Session')
def test_rp_client_start_with_overriding_launch_attributes(self, mock_session):
    rp_truncation_msg = 'Attribute values cannot exceed 128 characters in length. Value got: veryverylongattributevalue'
    mock_start = mock_session().post
    mock_start.side_effects = [
        lambda *args, **kwargs: mock.Mock(
            json=lambda: {"id": "mock_session_id"},
            status_code=200,
        ),
        lambda *args, **kwargs: mock.Mock(
            json=lambda: {"item_id": "mock_item_id"},
            status_code=200,
        ),
    ]

    client = RPClient('http://endpoint', 'default_personal', api_key='test_api_key',
                      project='default_personal', attributes=['some': 'attribute'])
    client.client = mock_session()

    with warning_handler(RPTruncationWarning) as wh:
        rp = step([('veryverylongattributename', 'veryverylongattributevalue')], lambda: None)
        expect(lambda: assert_that(rp, is_none()))
        expect(lambda: assert_that(mock_start.call_count, equal_to(2)))
        expect(lambda: assert_that(len(wh.warnings), equal_to(1)))
        expect(lambda: assert_that(str(wh.warnings[0]).startswith(rp_truncation_msg)))


@mock.patch('reportportal_client.aio.client.requests.Session')
def test_rp_client_start_with_invalid_attribute_type(self, mock_session):
    invalid_attribute = [{'invalid': {'invalid': 'attribute'}}]
    client = RPClient('http://endpoint', 'default_personal', api_key='test_api_key',
                      project='default_personal')
    client.client = mock_session()
    with pytest.raises(TypeError):
        client._create_payload_for_launch_start('Pytest', start_time='123', attributes=invalid_attribute)


@mock.patch('reportportal_client.aio.client.requests.Session')
def test_rp_client_start_with_invalid_attribute_structure(self, mock_session):
    invalid_attribute = [('invalid', {'invalid': 'attribute'})]
    client = RPClient('http://endpoint', 'default_personal', api_key='test_api_key',
                      project='default_personal')
    client.client = mock_session()
    with pytest.raises(ValueError):
        client._create_payload_for_launch_start('Pytest', start_time='123', attributes=invalid_attribute)


@mock.patch('reportportal_client.aio.client.requests.Session')
def test_rp_client_start_test_item(self, mock_session):
    mock_start_item = mock_session().post
    mock_start_item.return_value = mock.Mock(
        json=lambda: {"id": "TEST_ITEM_ID"},
        status_code=200
    )

    client = RPClient('http://endpoint', 'default_personal', api_key='test_api_key',
                      project='default_personal')
    client.client = mock_session()
    rp = step('old_school', client.start_test_item('Pytest', 'started', 'STEP'))
    expect(lambda: assert_that(rp, equal_to('TEST_ITEM_ID')))
    expect(lambda: assert_that(mock_start_item.call_count, equal_to(1)))
    expect(lambda: assert_that(mock_start_item.call_args[1]['name'], equal_to('Pytest')))
    expect(lambda: assert_that(mock_start_item.call_args[1]['parameters'], has_length(0)))


@mock.patch('reportportal_client.aio.client.requests.Session')
def test_rp_client_start_test_item_with_params(self, mock_session):
    mock_start_item = mock_session().post
    mock_start_item.return_value = mock.Mock(
        json=lambda: {"id": "TEST_ITEM_ID"},
        status_code=200
    )

    client = RPClient('http://endpoint', 'default_personal', api_key='test_api_key',
                      project='default_personal')
    client.client = mock_session()
    rp = step('old_school', lambda: client.start_test_item(
        'Pytest', 'started', 'STEP', parameters={"parameter": "param"}
    ))
    expect(lambda: assert_that(rp, equal_to('TEST_ITEM_ID')))
    expect(lambda: assert_that(mock_start_item.call_count, equal_to(1)))
    expect(lambda: assert_that(mock_start_item.call_args[1]['name'], equal_to('Pytest')))
    expect(lambda: assert_that(mock_start_item.call_args[1]['parameters'], equal_to({"parameter": "param"})))


@mock.patch('reportportal_client.aio.client.requests.Session')
def test_rp_client_finish_test_item(self, mock_session):
    mock_finish_item = mock_session().put
    mock_finish_item.return_value = mock.Mock(json=lambda: {}, status_code=200)

    client = RPClient('http://endpoint', 'default_personal', api_key='test_api_key',
                      project='default_personal')
    client.client = mock_session()
    rp = step('old_school', lambda: client.finish_test_item(
        'PYTEST_ITEM', 'finished', 'PASS'
    ))
    expect(lambda: assert_that(rp, is_none()))
    expect(lambda: assert_that(mock_finish_item.call_count, equal_to(1)))
    expect(lambda: assert_that(mock_finish_item.call_args[1]['name'], equal_to('PYTEST_ITEM')))


@mock.patch('reportportal_client.aio.client.requests.Session')
def test_rp_client_finish(self, mock_session):
    mock_finish = mock_session().put
    mock_finish.side_effects = [
        lambda *args, **kwargs: mock.Mock(
            json=lambda: {"id": "mock_session_id"},
            status_code=200,
        ),
        lambda *args, **kwargs: mock.Mock(
            json=lambda: {"item_id": "mock_item_id", 'response': 'mock_response'},
            status_code=200,
        ),
    ]

    client = RPClient('http://endpoint', 'default_personal', api_key='test_api_key',
                      project='default_personal')
    client.client = mock_session()
    client.launch_uuid = TEST_LAUNCH_ID
    rp = step('old_school', lambda: client.finish())
    expect(lambda: assert_that(rp, equal_to('mock_response')))
    expect(lambda: assert_that(mock_finish.call_count, equal_to(2)))
    expect(lambda: assert_that(mock_finish.call_args_list[0][1]['json']['end_time'], is_not(none())))


@mock.patch('reportportal_client.aio.client.requests.Session')
def test_rp_client_log(self, mock_session):
    my_binary_file = bytes([255] * 100000)
    my_text_content = 'X' * 100000
    my_binary_file_part = bytes([255] * 99999)
    my_text_content_part = 'X' * 99999

    mock_log = mock_session().post
    mock_log.side_effect = [lambda *_, **__: mock.Mock(
        status_code=200,
        reason=None,
        text=lambda: 'Session opened',
    ), lambda *_, **kws: mock.Mock(
        status_code=200,
        reason=None,
        text=lambda: f'request from {kws["files"][0][1].find(my_binary_file_part)}'
    ), lambda *_, **kws: mock.Mock(
        status_code=200,
        reason=None,
        text=lambda: kws["files"][0][1].find(my_text_content_part)
    )]

    client = RPClient('http://endpoint', 'default_personal', api_key='test_api_key',
                      project='default_personal')
    client.client = mock_session()

    rp_binary = step('old_school', lambda: client.log(time=str(step.TIME), message='binary message',
                                                     attachment=RPFile('binary_file', my_binary_file, 'application/octet-stream')))
    rp_text = step('old_school', lambda: client.log(time=str(step.TIME), message='text message',
                                                    attachment=RPFile('text_file', my_text_content, 'application/octet-stream')))
    rp_no_file = step('old_school', lambda: client.log(time=str(step.TIME), message='no file'))

    expect(lambda: assert_that(rp_binary, is_not-none()))
    expect(lambda: assert_that(mock_log.call_count, equal_to(3)))
    expect(lambda: assert_that(mock_log.call_args_list[1][1]['files'][0][1].find(my_binary_file_part), greater_than(-1)))
    expect(lambda: assert_that(mock_log.call_args_list[2][1]['files'][0][1].find(my_text_content_part), eq(-1)))

    expect(lambda: assert_that(rp_text, is_not_none()))
    expect(lambda: assert_that(mock_log.call_count, equal_to(3)))
    expect(lambda: assert_that(mock_log.call_args_list[1][1]['files'][0][1].find(my_binary_file_part), greater_than(-1)))
    expect(lambda: assert_that(mock_log.call_args_list[2][1]['files'][0][1].find(my_text_content_part), eq(-1)))

    expect(lambda: assert_that(rp_no_file, is_not_none()))
    expect(lambda: assert_that(mock_log.call_count, equal_to(3)))


@mock.patch('reportportal_client.aio.client.requests.Session')
def test_rp_client_update_item(self, mock_session):
    mock_update = mock_session().put
    mock_update.return_value = mock.Mock(json=lambda: {}, status_code=200)

    client = RPClient('http://endpoint', 'default_personal', api_key='test_api_key',
                      project='default_personal')
    client.client = mock_session()
    rp = step('old_school', lambda: client.update_test_item('MYITEM', attributes={'test': 'update'}))
    expect(lambda: assert_that(rp, is_none()))
    expect(lambda: assert_that(mock_update.call_count, equal_to(1)))
    expect(lambda: assert_that(mock_update.call_args[1]['name'], equal_to('MYITEM')))
    expect(lambda: assert_that(mock_update.call_args[1]['data'], has_key('attributes')))


@mock.patch('reportportal_client.aio.client.requests.Session')
def test_rp_client_finish_item_force_reconnect_attempt(self, mock_session):
    mock_finish = mock_session().post
    mock_finish.side_effect = [ConnectionError(), lambda *args, **kwargs: mock.Mock(
        json=lambda: {"id": "mock_session_id"},
        status_code=200,
    )]

    client = RPClient('http://endpoint', 'default_personal', api_key='test_api_key', connect_retries=-1,
                      reconnect_period=0.0,
                      project='default_personal')
    client.client = mock_session()
    client.launch_uuid = TEST_LAUNCH_ID
    rp = step('old_school', lambda: client.finish())
    expect(lambda: assert_that(rp, is_none()))
    expect(lambda: assert_that(mock_finish.call_count, equal_to(2)))


@mock.patch('reportportal_client.aio.client.requests.Session')
def test_rp_client_finish_item_force_reconnect_attempt_fail(self, mock_session):
    mock_finish = mock_session().post
    mock_finish.side_effect = [ConnectionError()]

    client = RPClient('http://endpoint', 'default_personal', api_key='test_api_key', connect_retries=-1,
                      reconnect_period=-1,
                      project='default_personal')
    client.client = mock_session()
    client.launch_uuid = TEST_LAUNCH_ID
    with pytest.raises(ConnectionError):
        rp = step('old_school', lambda: client.finish())
        assert rp is None
        assert mock_finish.call_count == 2


@mock.patch('reportportal_client.aio.client.requests.Session')
def test_rp_client_finish_item_incorrect_launch_id(self, mock_session):
    mock_finish = mock_session().post
    mock_finish.return_value = mock.Mock(json=lambda: {}, status_code=400)

    client = RPClient('http://endpoint', 'default_personal', api_key='test_api_key',
                      project='default_personal')
    client.client = mock_session()
    client.launch_uuid = 'INVALID_ID'
    rp = step('old_school', lambda: client.finish())
    expect(lambda: assert_that(rp, is_none()))
    expect(lambda: assert_that(mock_finish.call_count, equal_to(1)))


@mock.patch('reportportal_client.aio.client.requests.Session')
def test_rp_client_end_launch_incorrect_launch_id(self, mock_session):
    mock_finish = mock_session().post
    mock_finish.return_value = mock.Mock(json=lambda: {}, status_code=400)

    client = RPClient('http://endpoint', 'default_personal', api_key='test_api_key',
                      project='default_personal')
    client.client = mock_session()
    client.launch_uuid = 'INVALID_ID'
    rp = step('old_school', lambda: client.finish_launch(status='SUCCESS'))
    expect(lambda: assert_that(rp, is_none()))
    expect(lambda: assert_that(mock_finish.call_count, equal_to(0)))


@mock.patch('reportportal_client.aio.client.requests.Session')
def test_rp_client_finish_launch(self, mock_session):
    mock_finish = mock_session().post
    mock_finish.return_value = mock.Mock(json=lambda: {}, status_code=200)

    client = RPClient('http://endpoint', 'default_personal', api_key='test_api_key',
                      project='default_personal')
    client.client = mock_session()
    client.launch_uuid = TEST_LAUNCH_ID
    rp = step('old_school', lambda: client.finish_launch(status='SUCCESS'))
    expect(lambda: assert_that(rp, is_none()))
    expect(lambda: assert_that(mock_finish.call_count, equal_to(1)))
    expect(lambda: assert_that(mock_finish.call_args[1]['data'], has_key('status')))
    expect(lambda: assert_that(mock_finish.call_args[1]['data']['status'], equal_to('SUCCESS')))


@mock.patch('reportportal_client.aio.client.requests.Session')
def test_rp_client_set_rerun(self, mock_session):
    mock_finish = mock_session().post
    mock_finish.return_value = mock.Mock(json=lambda: {}, status_code=200)

    client = RPClient('http://endpoint', 'default_personal', api_key='test_api_key',
                      project='default_personal')
    client.client = mock_session()
    client.launch_uuid = TEST_LAUNCH_ID
    rp = step('old_school', lambda: client.finish_launch(rerun=True))
    expect(lambda: assert_that(rp, is_none()))
    expect(lambda: assert_that(mock_finish.call_count, equal_to(1)))
    expect(lambda: assert_that(mock_finish.call_args[1]['data'], has_key('rerun')))
    expect(lambda: assert_that(mock_finish.call_args[1]['data']['rerun'], equal_to(True)))


@mock.patch('reportportal_client.aio.client.requests.Session')
def test_rp_client_set_rerun_of(self, mock_session):
    mock_finish = mock_session().post
    mock_finish.return_value = mock.Mock(json=lambda: {}, status_code=200)

    rerun_id = "e2f52d0c6c31d4bfa0bceec6de488005"
    client = RPClient('http://endpoint', 'default_personal', api_key='test_api_key',
                      project='default_personal')
    client.client = mock_session()
    client.launch_uuid = TEST_LAUNCH_ID
    rp = step('old_school', lambda: client.finish_launch(rerun_of=rerun_id))
    expect(lambda: assert_that(rp, is_none()))
    expect(lambda: assert_that(mock_finish.call_count, equal_to(1)))
    expect(lambda: assert_that(mock_finish.call_args[1]['data'], has_key('rerun_of')))
    expect(lambda: assert_that(mock_finish.call_args[1]['data']['rerun_of'], equal_to(rerun_id)))


@mock.patch('reportportal_client.aio.client.requests.Session')
def test_rp_client_set_attributes(self, mock_session):
    mock_finish = mock_session().post
    mock_finish.return_value = mock.Mock(json=lambda: {}, status_code=200)

    client = RPClient('http://endpoint', 'default_personal', api_key='test_api_key',
                      project='default_personal')
    client.client = mock_session()
    client.launch_uuid = TEST_LAUNCH_ID
    client.set_test_attributes([{"key": "smoke", "value": "smoke"}])
    expect(lambda: assert_that(mock_finish.call_count, equal_to(1)))
    expect(lambda: assert_that(mock_finish.call_args[1]['data'], has_key('attributes')))
    expect(lambda: assert_that(mock_finish.call_args[1]['data']['attributes'], has_length(1)))


@mock.patch('reportportal_client.aio.client.requests.Session')
def test_rp_client_set_custom_attributes(self, mock_session):
    mock_finish = mock_session().post
    mock_finish.return_value = mock.Mock(json=lambda: {}, status_code=200)

    client = RPClient('http://endpoint', 'default_personal', api_key='test_api_key',
                      project='default_personal')
    client.client = mock_session()
    client.launch_uuid = TEST_LAUNCH_ID
    custom_attributes = [{"key": "smoke", "value": "smoke"}, {"value": "custom_attribute"}]
    client.set_test_attributes(custom_attributes)
    expect(lambda: assert_that(mock_finish.call_count, equal_to(1)))
    expect(lambda: assert_that(mock_finish.call_args[1]['data'], has_key('attributes')))
    expect(lambda: assert_that(mock_finish.call_args[1]['data']['attributes'], has_length(2)))


@mock.patch('reportportal_client.aio.client.requests.Session')
def test_rp_client_set_empty_attributes(self, mock_session):
    mock_finish = mock_session().post
    mock_finish.return_value = mock.Mock(json=lambda: {}, status_code=200)

    client = RPClient('http://endpoint', 'default_personal', api_key='test_api_key',
                      project='default_personal')
    client.client = mock_session()
    client.launch_uuid = TEST_LAUNCH_ID
    client.set_test_attributes([])
    expect(lambda: assert_that(mock_finish.call_count, equal_to(1)))
    expect(lambda: assert_that(mock_finish.call_args[1]['data'], has_key('attributes')))
    expect(lambda: assert_that(mock_finish.call_args[1]['data']['attributes'], has_length(0)))


@mock.patch('reportportal_client.aio.client.requests.Session')
def test_rp_client_set_attributes_without_values(self, mock_session):
    mock_finish = mock_session().post
    mock_finish.return_value = mock.Mock(json=lambda: {}, status_code=200)

    client = RPClient('http://endpoint', 'default_personal', api_key='test_api_key',
                      project='default_personal')
    client.client = mock_session()
    client.launch_uuid = TEST_LAUNCH_ID
    client.set_test_attributes([{}, {"not_set": None}, None])
    expect(lambda: assert_that(mock_finish.call_count, equal_to(1)))
    expect(lambda: assert_that(mock_finish.call_args[1]['data'], has_key('attributes')))
    expect(lambda: assert_that(mock_finish.call_args[1]['data']['attributes'], has_length(0)))


@mock.patch('reportportal_client.aio.client.requests.Session')
def test_rp_client_set_skipped_test_attributes(self, mock_session):
    mock_finish = mock_session().post
    mock_finish.return_value = mock.Mock(json=lambda: {}, status_code=200)

    client = RPClient('http://endpoint', 'default_personal', api_key='test_api_key',
                      project='default_personal')
    client.client = mock_session()
    client.launch_uuid = TEST_LAUNCH_ID
    client.set_test_attributes([])
    client.skip_issue = True
    client._is_skipped_an_issue = False
    client._skip_analytics = True
    client.finish()
    expect(lambda: assert_that(mock_finish.call_count, equal_to(1)))
    expect(lambda: assert_that(mock_finish.call_args[1]['data'], has_key('status')))
    expect(lambda: assert_that(mock_finish.call_args[1]['data']['status'], equal_to('SKIPPED')))


@mock.patch('reportportal_client.aio.client.requests.Session')
def test_rp_client_set_skipped_an_issue_test_attributes(self, mock_session):
    mock_finish = mock_session().post
    mock_finish.return_value = mock.Mock(json=lambda: {}, status_code=200)

    client = RPClient('http://endpoint', 'default_personal', api_key='test_api_key',
                      project='default_personal')
    client.client = mock_session()
    client.launch_uuid = TEST_LAUNCH_ID
    client.set_test_attributes(Issue('known_issue').payload['attributes'])
    client.skip_issue = True
    client._is_skipped_an_issue = True
    client._skip_analytics = True
    client.finish()
    expect(lambda: assert_that(mock_finish.call_count, equal_to(1)))
    expect(lambda: assert_that(mock_finish.call_args[1]['data'], has_key('status')))
    expect(lambda: assert_that(mock_finish.call_args[1]['data']['status'], equal_to('SKIPPED')))
    expect(lambda: assert_that(mock_finish.call_args[1]['data'], has_key('issues')))
    expect(lambda: assert_that(mock_finish.call_args[1]['data']['issues'], equal_to([])))


@mock.patch('reportportal_client.aio.client.requests.Session')
def test_rp_client_get_item_id_by_uuid(self, mock_session):
    get_item = mock_session().get
    get_item.return_value = mock.Mock(json=lambda: "TEST_ITEM_ID", status_code=200)

    client = RPClient('http://endpoint', 'default_personal', api_key='test_api_key',
                      project='default_personal')
    client.client = mock_session()
    item_id = step('old_school', lambda: client.get_item_id_by_uuid('MYITEM'))
    expect(lambda: assert_that(item_id, equal_to('TEST_ITEM_ID')))
    expect(lambda: assert_that(get_item.call_count, equal_to(1)))
    expect(lambda: assert_that(get_item.call_args[1]['params'], has_key('project')))
    expect(lambda: assert_that(get_item.call_args[1]['params'], has_key('uuid')))


@mock.patch('reportportal_client.aio.client.requests.Session')
def test_rp_client_get_launch_info(self, mock_session):
    get_launch = mock_session().get
    get_launch.return_value = mock.Mock(json=lambda: {"id": "TEST_LAUNCH_ID"}, status_code=200)

    client = RPClient('http://endpoint', 'default_personal', api_key='test_api_key',
                      project='default_personal')
    client.client = mock_session()
    rp = step('old_school', lambda: client.get_launch_info())
    expect(lambda: assert_that(rp, equal_to({"id": "TEST_LAUNCH_ID"})))
    expect(lambda: assert_that(get_launch.call_count, equal_to(1)))
    expect(lambda: assert_that(get_launch.call_args[1]['params'], has_key('project')))
    expect(lambda: assert_that(get_launch.call_args[1]['params'], has_key('launch_id')))


@mock.patch('reportportal_client.aio.client.requests.Session')
def test_rp_client_get_project_settings(self, mock_session):
    get_project_settings = mock_session().get
    get_project_settings.return_value = mock.Mock(json=lambda: {"project": "DEFAULT_PERSONAL"},
                                                   status_code=200)

    client = RPClient('http://endpoint', 'default_personal', api_key='test_api_key',
                      project='default_personal')
    client.client = mock_session()
    rp = step('old_school', lambda: client.get_project_settings())
    expect(lambda: assert_that(rp, equal_to({"project": "DEFAULT_PERSONAL"})))
    expect(lambda: assert_that(get_project_settings.call_count, equal_to(1)))
    expect(lambda: assert_that(get_project_settings.call_args[1]['params'], has_key('project')))


@mock.patch('reportportal_client.aio.client.requests.Session')
def test_rp_client_get_launch_ui_id(self, mock_session):
    get_launch = mock_session().get
    get_launch.return_value = mock.Mock(json=lambda: 42, status_code=200)

    client = RPClient('http://endpoint', 'default_personal', api_key='test_api_key',
                      project='default_personal')
    client.client = mock_session()
    client.launch_uuid = TEST_LAUNCH_ID
    rp = step('old_school', lambda: client.get_launch_ui_id())
    expect(lambda: assert_that(rp, equal_to(42)))
    expect(lambda: assert_that(get_launch.call_count, equal_to(1)))
    expect(lambda: assert_that(get_launch.call_args[1]['params'], has_key('project')))
    expect(lambda: assert_that(get_launch.call_args[1]['params'], has_key('launch_uuid')))


@mock.patch('reportportal_client.aio.client.requests.Session')
def test_rp_client_get_launch_ui_url(self, mock_session):
    client = RPClient('http://endpoint', 'default_personal', api_key='test_api_key',
                      project='default_personal')
    client.client = mock_session()
    client.launch_uuid = TEST_LAUNCH_ID
    rp = step('old_school', lambda: client.get_launch_ui_url())
    expect(lambda: assert_that(rp, is_none()))


@mock.patch('reportportal_client.aio.client.requests.Session')
def test_rp_client_get_launch_ui_url_empty_uuid(self, mock_session):
    client = RPClient('http://endpoint', 'default_personal', api_key='test_api_key',
                      project='default_personal')
    client.client = mock_session()
    client.launch_uuid = None
    rp = step('old_school', lambda: client.get_launch_ui_url())
    expect(lambda: assert_that(rp, is_none()))


@mock.patch('reportportal_client.aio.client.requests.Session')
def test_rp_client_get_launch_ui_url_with_filter_query_param(self, mock_session):
    client = RP_CLIENT_FILTER_LAUNCH_ID
    client.client = mock_session()
    rp = step('old_school', lambda: client.get_launch_ui_url())
    expect(lambda: assert_that(rp, starts_with(FILTER_QUERY_PARAM_EXPECTED_START)))


@mock.patch('reportportal_client.aio.client.requests.Session')
def test_rp_client_get_launch_ui_url_with_filter_query_param_via_constructor(self, mock_session):
    client = RPClient('http://endpoint', 'default_personal', api_key='test_api_key',
                      filter_attributes={'issue_id': TEST_LAUNCH_ID},
                      project='default_personal')
    client.client = mock_session()
    rp = step('old_school', lambda: client.get_launch_ui_url())
    expect(lambda: assert_that(rp, starts_with(FILTER_QUERY_PARAM_EXPECTED_START)))


@mock.patch('reportportal_client.aio.client.requests.Session')
def test_rp_client_get_launch_ui_url_with_filter_query_param_via_constructor_parent_id(self, mock_session):
    client = RPClient('http://endpoint', 'default_personal', api_key='test_api_id',
                      filter_attributes={'launch_id': TEST_LAUNCH_ID},
                      project='default_personal')
    client.client = mock_session()
    rp = step('old_school', lambda: client.get_launch_ui_url())
    expect(lambda: assert_that(rp, starts_with(FILTER_QUERY_PARAM_EXPECTED_START)))


@mock.patch('reportportal_client.aio.client.requests.Session')
def test_rp_client_get_launch_ui_url_with_filter_query_param_via_start_call(self, mock_session):
    client = RPClient('http://endpoint', 'default_personal', api_key='test_api_key',
                      project='default_personal')
    client.client = mock_session()
    client.start_launch('Pytest', now(), filter_attributes={'issue_id': TEST_LAUNCH_ID})
    rp = step('old_school', lambda: client.get_launch_ui_url())
    expect(lambda: assert_that(rp, starts_with(FILTER_QUERY_PARAM_EXPECTED_START)))


@mock.patch('reportportal_client.aio.client.requests.Session')
def test_rp_client_get_item_id_by_uuid_empty_uuid(self, mock_session):
    get_item = mock_session().get
    rp = step('old_school', lambda: RPClient('http://endpoint', 'default_personal', api_key='test_api_key',
                                             project='default_personal').get_item_id_by_uuid(None))
    expect(lambda: assert_that(rp, is_none()))
    expect(lambda: assert_that(get_item.call_count, equal_to(0)))


@mock.patch('reportportal_client.aio.client.requests.Session')
def test_rp_client_log_empty_message(self, mock_session):
    my_log = mock_session().post
    my_log.return_value = mock.Mock(status_code=200, reason=None, text=lambda: '')

    client = RPClient('http://endpoint', 'default_personal', api_key='test_api_key',
                      project='default_personal')
    client.client = mock_session()
    rp = step('old_school', lambda: client.log(time=str(step.TIME), message=None))
    expect(lambda: assert_that(rp, is_none()))
    expect(lambda: assert_that(my_log.call_count, equal_to(0)))


@mock.patch('reportportal_client.aio.client.requests.Session')
def test_rp_client_log_with_zero_length_message(self, mock_session):
    my_log = mock_session().post
    my_log.return_value = mock.Mock(status_code=200, reason=None, text=lambda: '')

    client = RPClient('http://endpoint', 'default_personal', api_key='test_api_key',
                      project='default_personal')
    client.client = mock_session()
    rp = step('old_school', lambda: client.log(time=str(step.TIME), message=''))
    expect(lambda: assert_that(rp, is_none()))
    expect(lambda: assert_that(my_log.call_count, equal_to(0)))


@mock.patch('reportportal_client.aio.client.requests.Session')
def test_rp_client_log_none(self, mock_session):
    my_log = mock_session().post
    my_log.return_value = mock.Mock(status_code=200, reason=None, text=lambda: '')

    client = RPClient('http://endpoint', 'default_personal', api_key='test_api_key',
                      project='default_personal')
    client.client = mock_session()
    rp = step('old_school', lambda: client.log(time=str(step.TIME), message=None))
    expect(lambda: assert_that(rp, is_none()))
    expect(lambda: assert_that(my_log.call_count, equal_to(0)))


@mock.patch('reportportal_client.aio.client.requests.Session')
def test_rp_client_start_launch_with_required(self, mock_session):
    mock_start_launch = mock_session().post
    mock_start_launch.return_value = mock.Mock(json=lambda: {"id": TEST_LAUNCH_ID}, status_code=200)

    client = RPClient('http://endpoint', 'default_personal', api_key='test_api_key',
                      project='default_personal')
    client.client = mock_session()
    rp = step('old_school', lambda: client.start_launch(name='Pytest', start_time=now()))
    expect(lambda: assert_that(rp, equal_to(TEST_LAUNCH_ID)))
    expect(lambda: assert_that(mock_start_launch.call_count, equal_to(1)))


@mock.patch('reportportal_client.aio.client.requests.Session')
def test_rp_client_start_launch_rerun(self, mock_session):
    mock_start_launch = mock_session().post
    mock_start_launch.return_value = mock.Mock(json=lambda: {"id": TEST_LAUNCH_ID}, status_code=200)

    client = RPClient('http://endpoint', 'default_personal', api_key='test_api_key',
                      project='default_personal')
    client.client = mock_session()
    rp = step('old_school', lambda: client.start_launch(name='Pytest', start_time=now(), rerun=True,
                                                        rerun_of=TEST_LAUNCH_ID))
    expect(lambda: assert_that(rp, equal_to(TEST_LAUNCH_ID)))
    expect(lambda: assert_that(mock_start_launch.call_count, equal_to(1)))


@mock.patch('reportportal_client.aio.client.requests.Session')
def test_rp_client_start_launch_rerun_without_rerun_of(self, mock_session):
    mock_start_launch = mock_session().post

    client = RPClient('http://endpoint', 'default_personal', api_key='test_api_key',
                      project='default_personal')
    client.client = mock_session()
    with pytest.raises(RPInvalidRequestError):
        rp = step('old_school', lambda: client.start_launch(name='Pytest', start_time=now(), rerun=True))
        expect(lambda: assert_that(rp, is_none()))
        expect(lambda: assert_that(mock_start_launch.call_count, equal_to(0)))


@mock.patch('reportportal_client.aio.client.requests.Session')
def test_rp_client_start_launch_invalid_arguments(self, mock_session):
    mock_start_launch = mock_session().post

    client = RPClient('http://endpoint', 'default_personal', api_key='test_api_key',
                      project='default_personal')
    client.client = mock_session()
    with pytest.warns(DeprecationWarning):
        rp = step('old_school', lambda: client.start_launch(name='Pytest', start_time=now(), url='http://test'))
        expect(lambda: assert_that(rp, is_none()))
        expect(lambda: assert_that(mock_start_launch.call_count, equal_to(0)))


@mock.patch('reportportal_client.aio.client.requests.Session')
def test_rp_client_clone(self, mock_session):
    mock_start_launch = mock_session().post
    mock_start_launch.return_value = mock.Mock(json=lambda: {"id": "CLONED_LAUNCH_ID"}, status_code=200)

    client = RPClient('http://endpoint', 'default_personal', api_key='test_api_key',
                      project='default_personal')
    client.client = mock_session()
    cloned_client = step('old_school', lambda: client.clone())
    expect(lambda: assert_that(cloned_client, is_not_none()))
    expect(lambda: assert_that(mock_start_launch.call_count, equal_to(1)))
    expect(lambda: assert_that(cloned_client.launch_uuid, 'CLONED_LAUNCH_ID'))
    expect(lambda: assert_that(id(client), is_not_(id(cloned_client))))


@mock.patch('reportportal_client.aio.client.requests.Session')
def test_rp_client_clone_incorrect_parent_client(self, mock_session):
    parent_client = RPClient('http://endpoint', 'default_personal', api_key='test_api_key',
                             project='default_personal')
    parent_client.client = None
    with pytest.raises(AssertionError):
        step('old_school', lambda: parent_client.clone())


@mock.patch('reportportal_client.aio.client.requests.Session')
def test_rp_client_clone_incorrect_parent_client_launch_uuid(self, mock_session):
    parent_client = RPClient('http://endpoint', 'default_personal', api_key='test_api_key',
                             project='default_personal')
    parent_client.client = mock_session()
    parent_client.launch_uuid = None
    with pytest.raises(RPIncorrectParentLaunchState):
        step('old_school', lambda: parent_client.clone())


@mock.patch('reportportal_client.aio.client.requests.Session')
def test_rp_client_clone_attributes(self, mock_session):
    mock_start_launch = mock_session().post
    mock_start_launch.return_value = mock.Mock(json=lambda: {"id": "CLONED_LAUNCH_ID"}, status_code=200)

    client = RPClient('http://endpoint', 'default_personal', api_key='test_api_key',
                      rerun=True, rerun_of=TEST_LAUNCH_ID, attributes=["attribute"], description="description",
                      project='default_personal')
    client.client = mock_session()
    cloned_client = step('old_school', lambda: client.clone())
    clone_start_request = HttpRequest.make_json_request(mock_start_launch, 'POST', "/launch/restart")
    expect(lambda: assert_that(clone_start_request, is_not_none()))
    expect(lambda: assert_that(clone_start_request, has_key('data')))
    expect(lambda: assert_that(clone_start_request.data, has_key('rerun')))
    expect(lambda: assert_that(clone_start_request.data, has_key('rerun_of')))
    expect(lambda: assert_that(clone_start_request.data, has_key('attributes')))
    expect(lambda: assert_that(clone_start_request.data, has_key('description')))


@mock.patch('reportportal_client.aio.client.requests.Session')
def test_rp_client_clone_launch_uuid_print(self, mock_client):
    mock_client = RPClient('http://endpoint', 'default_personal', api_key='test_api_key',
                           launch_uuid_print=True, print_output=OutputType.STDOUT)
    mock_client.client = mock_client
    cloned_client = step('old_school', lambda: mock_client.clone())
    expect(lambda: assert_that(cloned_client.launch_uuid_print, True))


@mock.patch('reportportal_client.aio.client.requests.Session')
def test_rp_client_clone_rp(self, mock_client):
    rp_client = RP('http://endpoint', 'default_personal', api_key='test_api_key',
                   launch_uuid=TEST_LAUNCH_ID, project='default_personal')
    rp_client.client = mock_client
    cloned_client = step('old_school', lambda: rp_client.clone())
    expect(lambda: assert_that(cloned_client.launch_uuid_print, None))


@mock.patch('reportportal_client.aio.client.requests.Session')
def test_rp_client_clone_rp_incorrect(self, mock_client):
    rp_client = RP('http://endpoint', 'default_personal', api_key='test_api_key', project='default_personal')
    cloned_client = step('old_school', lambda: rp_client.clone())
    expect(lambda: assert_that(cloned_client, None))


@mock.patch('reportportal_client.aio.client.requests.Session')
def test_rp_client_clone_rp_client_is_none(self, mock_client):
    rp_client = RP('http://endpoint', 'default_personal', api_key='test_api_key', project='default_personal')
    rp_client.client = None
    with pytest.raises(AssertionError):
        step('old_school', lambda: rp_client.clone())


@mock.patch('reportportal_client.aio.client.requests.Session')
def test_rp_client_clone_attributes_rerun(self, mock_session):
    mock_start_launch = mock_session().post
    mock_start_launch.return_value = mock.Mock(json=lambda: {"id": "CLONED_LAUNCH_ID"}, status_code=200)

    client = RPClient('http://endpoint', 'default_personal', api_key='test_api_key',
                      attributes=["attribute"], description="description",
                      project='default_personal')
    client.client = mock_session()
    cloned_client = step('old_school', lambda: client.clone())
    clone_start_request = HttpRequest.make_json_request(mock_start_launch, 'POST', "/launch/restart")
    expect(lambda: assert_that(clone_start_request, is_not_none()))
    expect(lambda: assert_that(clone_start_request, has_key('data')))
    expect(lambda: assert_that(clone_start_request.data, has_key('rerun')))
    expect(lambda: assert_that(clone_start_request.data, has_no_key('rerun_of')))
    expect(lambda: assert_that(clone_start_request.data, has_no_key('attributes')))
    expect(lambda: assert_that(clone_start_request.data, has_no_key('description')))


@mock.patch('reportportal_client.aio.client.requests.Session')
def test_rp_client_clone_no_attributes(self, mock_session):
    mock_start_launch = mock_session().post
    mock_start_launch.return_value = mock.Mock(json=lambda: {"id": "CLONED_LAUNCH_ID"}, status_code=200)

    client = RPClient('http://endpoint', 'default_personal', api_key='test_api_key',
                      project='default_personal')
    client.client = mock_session()
    cloned_client = step('old_school', lambda: client.clone())
    clone_start_request = HttpRequest.make_json_request(mock_start_launch, 'POST', "/launch/restart")
    expect(lambda: assert_that(clone_start_request, is_not_none()))
    expect(lambda: assert_that(clone_start_request, has_key('data')))
    expect(lambda: assert_that(clone_start_request.data, has_no_key('rerun')))
    expect(lambda: assert_that(clone_start_request.data, has_no_key('rerun_of')))
    expect(lambda: assert_that(clone_start_request.data, has_no_key('attributes')))
    expect(lambda: assert_that(clone_start_request.data, has_no_key('description')))


@mock.patch('reportportal_client.aio.client.requests.Session')
def test_rp_client_clone_launch_uuid_print_incorrect(self, mock_client):
    rp_client = RP('http://endpoint', 'default_personal', api_key='test_api_key', launch_uuid_print=True,
                   print_output=OutputType.STDOUT)
    cloned_client = step('old_school', lambda: rp_client.clone())
    expect(lambda: assert_that(cloned_client.launch_uuid_print, None))


@mock.patch('reportportal_client.aio.client.requests.Session')
def test_rp_client_close(self, close_mock):
    client = RPClient('http://endpoint', 'default_personal', api_key='test_api_key',
                      project='default_personal')
    client.client = 'SESSION'
    step('old_school', lambda: client.close())
    expect(lambda: assert_that(close_mock.call_count, equal_to(1)))


@mock.patch('reportportal_client.aio.client.requests.Session')
def test_rp_client_shutdown_before_launch_finish(self, close_mock):
    client = RPClient('http://endpoint', 'default_personal', api_key='test_api_key',
                      project='default_personal')
    client.client = 'SESSION'
    client.launch_uuid = TEST_LAUNCH_ID
    step('old_school', lambda: client.shutdown())
    expect(lambda: assert_that(close_mock.call_count, equal_to(1)))


@mock.patch('reportportal_client.aio.client.requests.Session')
def test_rp_client_shutdown_during_launch_finish(self, close_mock):
    client = RPClient('http://endpoint', 'default_personal', api_key='test_api_key',
                      project='default_personal')
    client.client = 'SESSION'
    def_func = lambda: None
    def_func.finish = lambda: step('old_school', lambda: None)
    client.finish = def_func
    client.launch_uuid = TEST_LAUNCH_ID
    step('old_school', lambda: client.shutdown())
    expect(lambda: assert_that(close_mock.call_count, equal_to(1)))


@mock.patch('reportportal_client.aio.client.requests.Session')
def test_rp_client_shutdown_after_launch_finish(self, close_mock):
    client = RPClient('http://endpoint', 'default_notification', api_key='test_api_key',
                      project='default_personal')
    client.client = 'SESSION'
    client.finish = lambda: step('old_school', lambda: None)
    client.launch_uuid = None
    step('old_school', lambda: client.shutdown())
    expect(lambda: assert_that(close_mock.call_count, equal_to(1)))


@mock.patch('reportportal_client.aio.client.requests.Session')
def test_rp_client_shutdown_exception_in_during_launch_finish(self, close_mock):
    def_finish = lambda: step('old_school', lambda: Exception('test exception'))
    client = RPClient('http://endpoint', 'default_notification', api_key='test_api_key',
                      project='default_personal')
    client.finish = def_finish
    client.client = 'SESSION'
    client.launch_uuid = TEST_LAUNCH_ID
    step('old_school', lambda: client.shutdown())
    expect(lambda: assert_that(close_mock.call_count, equal_to(1)))


@mock.patch('reportportal_client.aio.client.requests.Session')
def test_rp_client_shutdown_exception_in_after_launch_finish(self, close_mock):
    def_finish = lambda: step('old_school', lambda: None)
    client = RPClient('http://endpoint', 'default_notification', api_key='test_api_key',
                      project='default_personal')
    client.finish = def_finish
    client.client = 'SESSION'
    client.launch_uuid = None
    step('old_school', lambda: client.shutdown())
    expect(lambda: assert_that(close_mock.call_count, equal_to(1)))


@mock.patch('reportportal_client.aio.client.requests.Session')
def test_rp_client_shutdown_exception_in_before_launch_finish(self, close_mock):
    client = RPClient('http://endpoint', 'default_notification', api_key='test_api_key',
                      project='default_personal')
    def_finish = lambda: step('old_school', lambda: Exception('test exception'))
    client.finish = def_finish
    client.client = 'SESSION'
    client.launch_uuid = TEST_LAUNCH_ID
    step('old_school', lambda: client.shutdown())
    expect(lambda: assert_that(close_mock.call_count, equal_to(1)))


@mock.patch('reportportal_client.aio.client.requests.Session')
def test_rp_client_shutdown_twice(self, close_mock):
    client = RPClient('http://endpoint', 'default_notification', api_key='test_api_key',
                      project='default_personal')
    client.client = 'SESSION'
    client.launch_uuid = TEST_LAUNCH_ID
    step('old_school', lambda: client.shutdown())
    step('old_school', lambda: client.shutdown())
    expect(lambda: assert_that(close_mock.call_count, equal_to(1)))


@mock.patch('reportportal_client.aio.client.requests.Session')
def test_rp_client_shutdown_thread_killed(self, close_mock):
    client = RPClient('http://endpoint', 'default_notification', api_key='test_api_key',
                      project='default_personal')
    client.client = 'SESSION'
    client.launch_uuid = TEST_LAUNCH_ID
    step('old_school', lambda: sys.exit(0))
    expect(lambda: assert_that(close_mock.call_count, equal_to(0)))
