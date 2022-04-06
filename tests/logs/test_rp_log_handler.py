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
import re

import pytest
from six.moves import mock

from reportportal_client._local import set_current
from reportportal_client.logs import RPLogHandler, RPLogger


@pytest.mark.parametrize(
    'logger_name, filter_logs,expected_result',
    [
        ('reportportal_client', False, True),
        ('reportportal_client', True, False),
        ('some_logger', False, True),
        ('some_logger', True, True)
    ]
)
@mock.patch('reportportal_client.logs.logging.Logger.handle')
def test_filter_client_logs(mocked_handle, logger_name, filter_logs,
                            expected_result):
    RPLogger(logger_name).info('test message')
    record = mocked_handle.call_args[0][0]

    log_handler = RPLogHandler(filter_client_logs=filter_logs)
    assert log_handler.filter(record) == expected_result


@pytest.mark.parametrize(
    'hostname, expected_result',
    [
        ('localhost', True),
        ('docker.local', False)
    ]
)
@mock.patch('reportportal_client.logs.logging.Logger.handle')
def test_filter_by_endpoint(mocked_handle, hostname, expected_result):
    RPLogger('urllib3.connectionpool').info(hostname + ': test message')
    record = mocked_handle.call_args[0][0]
    log_handler = RPLogHandler(
        filter_client_logs=True,
        endpoint='http://docker.local:8080'
    )
    assert log_handler.filter(record) == expected_result


@mock.patch('reportportal_client.logs.logging.Logger.handle')
def test_emit_simple(mocked_handle):
    test_message = 'test message'
    RPLogger('test_logger').info(test_message)
    record = mocked_handle.call_args[0][0]

    item_id = 'item_id'
    mock_client = mock.Mock()
    mock_client.current_item.side_effect = lambda: item_id
    set_current(mock_client)

    log_handler = RPLogHandler()
    log_handler.emit(record)

    assert mock_client.log.call_count == 1
    call_args = mock_client.log.call_args[0]
    call_kwargs = mock_client.log.call_args[1]

    assert re.match('^[0-9]+$', call_args[0])
    assert test_message == call_args[1]
    assert call_kwargs['level'] == 'INFO'
    assert not call_kwargs['attachment']
    assert call_kwargs['item_id'] == item_id


@mock.patch('reportportal_client.logs.logging.Logger.handle')
def test_emit_custom_level(mocked_handle):
    test_message = 'test message'
    RPLogger('test_logger').log(30, test_message)
    record = mocked_handle.call_args[0][0]

    mock_client = mock.Mock()
    set_current(mock_client)

    log_handler = RPLogHandler()
    log_handler.emit(record)
    assert mock_client.log.call_count == 1
    call_kwargs = mock_client.log.call_args[1]
    assert call_kwargs['level'] == 'WARN'
