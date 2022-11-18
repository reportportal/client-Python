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
import sys
import logging
import inspect
from logging import LogRecord

import pytest
from six.moves import mock

from reportportal_client._local import set_current
from reportportal_client.logs import RPLogger, RPLogHandler


def verify_record(logger_handler):
    assert logger_handler.call_count == 1
    call_args = logger_handler.call_args[0]
    assert len(call_args) == 1
    record = call_args[0]
    assert isinstance(record, LogRecord)
    return record


@mock.patch('reportportal_client.logs.logging.Logger.handle')
def test_record_make(logger_handler):
    logger = RPLogger('test_logger')
    logger.info('test_log')
    record = verify_record(logger_handler)
    assert not getattr(record, 'attachment')


@mock.patch('reportportal_client.logs.logging.Logger.handle')
def test_record_attachment(logger_handler):
    logger = RPLogger('test_logger')
    attachment = {'name': 'test.txt', 'content': 'test',
                  'content_type': 'text/plain'}
    logger.info('test_log', attachment=attachment)
    record = verify_record(logger_handler)
    result_attachment = getattr(record, 'attachment')
    assert result_attachment
    assert result_attachment == attachment


@pytest.mark.parametrize(
    'handler_level, log_level, expected_calls',
    [
        (logging.WARN, 'info', 0),
        (logging.INFO, 'info', 1),
    ]
)
def test_log_level_filter(handler_level, log_level, expected_calls):
    mock_client = mock.Mock()
    set_current(mock_client)

    logger = RPLogger('test_logger')
    logger.addHandler(RPLogHandler(level=handler_level))
    getattr(logger, log_level)('test_log')

    assert mock_client.log.call_count == expected_calls


@pytest.skipif(sys.version_info < (3, 8), '"stacklevel" introduced in Python 3.8, so not actual for earlier versions')
@mock.patch('reportportal_client.logs.logging.Logger.handle')
def test_stacklevel_record_make(logger_handler):
    logger = RPLogger('test_logger')
    logger.error('test_log', exc_info=RuntimeError('test'), stack_info=inspect.stack(), stacklevel=2)
    record = verify_record(logger_handler)
    assert record.stack_info.endswith('return func(*newargs, **newkeywargs)')
