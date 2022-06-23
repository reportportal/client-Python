#  Copyright (c) 2022 EPAM Systems
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


from six.moves import mock

from reportportal_client import helpers
from reportportal_client.core.log_manager import LogManager

RP_URL = 'http://docker.local:8080'
API_VERSION = 'api/v2'
TEST_LAUNCH_ID = 'test_launch_id'
TEST_ITEM_ID = 'test_item_id'
PROJECT_NAME = 'test_project'
KILOBYTE = 2 ** 10
MEGABYTE = KILOBYTE ** KILOBYTE
ABOVE_LIMIT_SIZE = MEGABYTE * 65
TEST_MASSAGE = 'test_message'
TEST_LEVEL = 'DEBUG'
TEST_BATCH_SIZE = 5


# noinspection PyUnresolvedReferences
def test_log_batch_send_by_length():
    session = mock.Mock()
    log_manager = LogManager(RP_URL, session, API_VERSION, TEST_LAUNCH_ID,
                             PROJECT_NAME, max_entry_number=TEST_BATCH_SIZE,
                             verify_ssl=False)
    log_manager._worker = mock.Mock()

    for _ in range(TEST_BATCH_SIZE):
        log_manager.log(helpers.timestamp(), TEST_MASSAGE, TEST_LEVEL,
                        item_id=TEST_ITEM_ID)

    assert log_manager._worker.send.call_count == 1
    batch = log_manager._worker.send.call_args[0][0]
    assert len(batch.log_reqs) == 5
    assert batch.http_request is not None
    assert 'post' in session._mock_children
    assert len(log_manager._batch) == 0
    assert log_manager._payload_size == helpers.TYPICAL_MULTIPART_FOOTER_LENGTH


# noinspection PyUnresolvedReferences
def test_log_batch_not_send_by_length():
    session = mock.Mock()
    log_manager = LogManager(RP_URL, session, API_VERSION, TEST_LAUNCH_ID,
                             PROJECT_NAME, max_entry_number=TEST_BATCH_SIZE,
                             verify_ssl=False)
    log_manager._worker = mock.Mock()

    for _ in range(TEST_BATCH_SIZE - 1):
        log_manager.log(helpers.timestamp(), TEST_MASSAGE, TEST_LEVEL,
                        item_id=TEST_ITEM_ID)

    assert log_manager._worker.send.call_count == 0
    assert 'post' not in session._mock_children
    assert len(log_manager._batch) == 4
    assert log_manager._payload_size > helpers.TYPICAL_MULTIPART_FOOTER_LENGTH


# noinspection PyUnresolvedReferences
def test_log_batch_send_by_stop():
    session = mock.Mock()
    log_manager = LogManager(RP_URL, session, API_VERSION, TEST_LAUNCH_ID,
                             PROJECT_NAME, max_entry_number=TEST_BATCH_SIZE,
                             verify_ssl=False)
    log_manager._worker = mock.Mock()

    for _ in range(TEST_BATCH_SIZE - 1):
        log_manager.log(helpers.timestamp(), TEST_MASSAGE, TEST_LEVEL,
                        item_id=TEST_ITEM_ID)
    log_manager.stop()

    assert log_manager._worker.send.call_count == 1
    batch = log_manager._worker.send.call_args[0][0]
    assert len(batch.log_reqs) == 4
    assert batch.http_request is not None
    assert 'post' in session._mock_children
    assert len(log_manager._batch) == 0
    assert log_manager._payload_size == helpers.TYPICAL_MULTIPART_FOOTER_LENGTH
