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

import json
import os
from unittest import mock

from reportportal_client import helpers
from reportportal_client.core.rp_requests import HttpRequest
from reportportal_client.logs import MAX_LOG_BATCH_PAYLOAD_SIZE
from reportportal_client.logs.log_manager import LogManager

RP_URL = "http://docker.local:8080"
API_VERSION = "v2"
TEST_LAUNCH_ID = "test_launch_id"
TEST_ITEM_ID = "test_item_id"
PROJECT_NAME = "test_project"
TEST_MASSAGE = "test_message"
TEST_LEVEL = "DEBUG"
TEST_BATCH_SIZE = 5
TEST_ATTACHMENT_NAME = "test_file.bin"
TEST_ATTACHMENT_TYPE = "application/zip"


# noinspection PyUnresolvedReferences
def test_log_batch_send_by_length():
    session = mock.Mock()
    log_manager = LogManager(
        RP_URL, session, API_VERSION, TEST_LAUNCH_ID, PROJECT_NAME, max_entry_number=TEST_BATCH_SIZE, verify_ssl=False
    )
    log_manager._worker = mock.Mock()

    for _ in range(TEST_BATCH_SIZE):
        log_manager.log(helpers.timestamp(), TEST_MASSAGE, TEST_LEVEL, item_id=TEST_ITEM_ID)

    assert log_manager._worker.send.call_count == 1
    batch = log_manager._worker.send.call_args[0][0]
    assert isinstance(batch, HttpRequest)
    assert len(json.loads(batch.files[0][1][1])) == 5
    assert "post" in session._mock_children
    assert len(log_manager._batch) == 0
    assert log_manager._payload_size == helpers.TYPICAL_MULTIPART_FOOTER_LENGTH


# noinspection PyUnresolvedReferences
def test_log_batch_send_url_format():
    session = mock.Mock()
    log_manager = LogManager(
        RP_URL + "/",
        session,
        API_VERSION,
        TEST_LAUNCH_ID,
        PROJECT_NAME,
        max_entry_number=TEST_BATCH_SIZE,
        verify_ssl=False,
    )
    log_manager._worker = mock.Mock()

    for _ in range(TEST_BATCH_SIZE):
        log_manager.log(helpers.timestamp(), TEST_MASSAGE, TEST_LEVEL, item_id=TEST_ITEM_ID)

    assert log_manager._worker.send.call_count == 1
    batch = log_manager._worker.send.call_args[0][0]
    assert isinstance(batch, HttpRequest)
    assert batch.url == RP_URL + "/api/" + API_VERSION + "/" + PROJECT_NAME + "/log"


# noinspection PyUnresolvedReferences
def test_log_batch_not_send_by_length():
    session = mock.Mock()
    log_manager = LogManager(
        RP_URL, session, API_VERSION, TEST_LAUNCH_ID, PROJECT_NAME, max_entry_number=TEST_BATCH_SIZE, verify_ssl=False
    )
    log_manager._worker = mock.Mock()

    for _ in range(TEST_BATCH_SIZE - 1):
        log_manager.log(helpers.timestamp(), TEST_MASSAGE, TEST_LEVEL, item_id=TEST_ITEM_ID)

    assert log_manager._worker.send.call_count == 0
    assert "post" not in session._mock_children
    assert len(log_manager._batch) == 4
    assert log_manager._payload_size > helpers.TYPICAL_MULTIPART_FOOTER_LENGTH


# noinspection PyUnresolvedReferences
def test_log_batch_send_by_stop():
    session = mock.Mock()
    log_manager = LogManager(
        RP_URL, session, API_VERSION, TEST_LAUNCH_ID, PROJECT_NAME, max_entry_number=TEST_BATCH_SIZE, verify_ssl=False
    )
    log_manager._worker = mock.Mock()

    for _ in range(TEST_BATCH_SIZE - 1):
        log_manager.log(helpers.timestamp(), TEST_MASSAGE, TEST_LEVEL, item_id=TEST_ITEM_ID)
    log_manager.stop()

    assert log_manager._worker.send.call_count == 1
    batch = log_manager._worker.send.call_args[0][0]
    assert isinstance(batch, HttpRequest)
    assert len(json.loads(batch.files[0][1][1])) == 4
    assert "post" in session._mock_children
    assert len(log_manager._batch) == 0
    assert log_manager._payload_size == helpers.TYPICAL_MULTIPART_FOOTER_LENGTH


# noinspection PyUnresolvedReferences
def test_log_batch_not_send_by_size():
    session = mock.Mock()
    log_manager = LogManager(
        RP_URL, session, API_VERSION, TEST_LAUNCH_ID, PROJECT_NAME, max_entry_number=TEST_BATCH_SIZE, verify_ssl=False
    )
    log_manager._worker = mock.Mock()

    headers_size = helpers.TYPICAL_MULTIPART_FOOTER_LENGTH - len(
        helpers.TYPICAL_FILE_PART_HEADER.format(TEST_ATTACHMENT_NAME, TEST_ATTACHMENT_TYPE)
    )
    attachment_size = MAX_LOG_BATCH_PAYLOAD_SIZE - headers_size - 1024
    random_byte_array = bytearray(os.urandom(attachment_size))
    attachment = {"name": TEST_ATTACHMENT_NAME, "content": random_byte_array, "content_type": TEST_ATTACHMENT_TYPE}

    log_manager.log(helpers.timestamp(), TEST_MASSAGE, TEST_LEVEL, item_id=TEST_ITEM_ID, attachment=attachment)
    log_manager.log(helpers.timestamp(), TEST_MASSAGE, TEST_LEVEL, item_id=TEST_ITEM_ID)

    assert log_manager._worker.send.call_count == 0
    assert "post" not in session._mock_children
    assert len(log_manager._batch) == 2
    assert log_manager._payload_size > MAX_LOG_BATCH_PAYLOAD_SIZE - 1024
    assert log_manager._payload_size < MAX_LOG_BATCH_PAYLOAD_SIZE


# noinspection PyUnresolvedReferences
def test_log_batch_send_by_size():
    session = mock.Mock()
    log_manager = LogManager(
        RP_URL, session, API_VERSION, TEST_LAUNCH_ID, PROJECT_NAME, max_entry_number=TEST_BATCH_SIZE, verify_ssl=False
    )
    log_manager._worker = mock.Mock()

    random_byte_array = bytearray(os.urandom(MAX_LOG_BATCH_PAYLOAD_SIZE))
    attachment = {"name": TEST_ATTACHMENT_NAME, "content": random_byte_array, "content_type": TEST_ATTACHMENT_TYPE}

    log_manager.log(helpers.timestamp(), TEST_MASSAGE, TEST_LEVEL, item_id=TEST_ITEM_ID, attachment=attachment)
    log_manager.log(helpers.timestamp(), TEST_MASSAGE, TEST_LEVEL, item_id=TEST_ITEM_ID)

    assert log_manager._worker.send.call_count == 1
    batch = log_manager._worker.send.call_args[0][0]
    assert isinstance(batch, HttpRequest)
    assert len(json.loads(batch.files[0][1][1])) == 1
    assert "post" in session._mock_children
    assert len(log_manager._batch) == 1
    assert log_manager._payload_size < helpers.TYPICAL_MULTIPART_FOOTER_LENGTH + 1024


# noinspection PyUnresolvedReferences
def test_log_batch_triggers_previous_request_to_send():
    session = mock.Mock()
    log_manager = LogManager(
        RP_URL, session, API_VERSION, TEST_LAUNCH_ID, PROJECT_NAME, max_entry_number=TEST_BATCH_SIZE, verify_ssl=False
    )
    log_manager._worker = mock.Mock()

    random_byte_array = bytearray(os.urandom(MAX_LOG_BATCH_PAYLOAD_SIZE))
    attachment = {"name": TEST_ATTACHMENT_NAME, "content": random_byte_array, "content_type": TEST_ATTACHMENT_TYPE}

    log_manager.log(helpers.timestamp(), TEST_MASSAGE, TEST_LEVEL, item_id=TEST_ITEM_ID)
    payload_size = log_manager._payload_size
    assert payload_size < helpers.TYPICAL_MULTIPART_FOOTER_LENGTH + 1024

    log_manager.log(helpers.timestamp(), TEST_MASSAGE, TEST_LEVEL, item_id=TEST_ITEM_ID, attachment=attachment)

    assert log_manager._worker.send.call_count == 1
    batch = log_manager._worker.send.call_args[0][0]
    assert isinstance(batch, HttpRequest)
    assert len(json.loads(batch.files[0][1][1])) == 1
    assert "post" in session._mock_children
    assert len(log_manager._batch) == 1
    assert log_manager._payload_size > MAX_LOG_BATCH_PAYLOAD_SIZE
