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

import os

from reportportal_client import helpers
# noinspection PyProtectedMember
from reportportal_client._internal.logs.batcher import LogBatcher
from reportportal_client.core.rp_file import RPFile
from reportportal_client.core.rp_requests import RPRequestLog
from reportportal_client.logs import MAX_LOG_BATCH_PAYLOAD_SIZE

TEST_LAUNCH_ID = "test_launch_uuid"
TEST_ITEM_ID = "test_item_id"
PROJECT_NAME = "test_project"
TEST_MASSAGE = "test_message"
TEST_LEVEL = "DEBUG"
TEST_BATCH_SIZE = 5
TEST_ATTACHMENT_NAME = "test_file.bin"
TEST_ATTACHMENT_TYPE = "application/zip"


def test_log_batch_send_by_length():
    log_batcher = LogBatcher(entry_num=TEST_BATCH_SIZE)

    for i in range(TEST_BATCH_SIZE):
        result = log_batcher.append(
            RPRequestLog(
                launch_uuid=TEST_LAUNCH_ID,
                time=helpers.timestamp(),
                message=TEST_MASSAGE,
                level=TEST_LEVEL,
                item_uuid=TEST_ITEM_ID,
            )
        )
        if i < TEST_BATCH_SIZE - 1:
            assert result is None
            assert len(log_batcher._batch) == i + 1
            assert log_batcher._payload_size > 0
        else:
            assert len(result) == TEST_BATCH_SIZE
            assert len(log_batcher._batch) == 0
            assert log_batcher._payload_size == 0


def test_log_batch_send_by_flush():
    log_batcher = LogBatcher(entry_num=TEST_BATCH_SIZE)

    for _ in range(TEST_BATCH_SIZE - 1):
        log_batcher.append(
            RPRequestLog(
                launch_uuid=TEST_LAUNCH_ID,
                time=helpers.timestamp(),
                message=TEST_MASSAGE,
                level=TEST_LEVEL,
                item_uuid=TEST_ITEM_ID,
            )
        )
    result = log_batcher.flush()

    assert len(result) == TEST_BATCH_SIZE - 1
    assert len(log_batcher._batch) == 0
    assert log_batcher._payload_size == 0


def test_log_batch_send_by_size():
    log_batcher = LogBatcher(entry_num=TEST_BATCH_SIZE)

    random_byte_array = bytearray(os.urandom(MAX_LOG_BATCH_PAYLOAD_SIZE))
    binary_result = log_batcher.append(
        RPRequestLog(
            launch_uuid=TEST_LAUNCH_ID,
            time=helpers.timestamp(),
            message=TEST_MASSAGE,
            level=TEST_LEVEL,
            item_uuid=TEST_ITEM_ID,
            file=RPFile(name=TEST_ATTACHMENT_NAME, content=random_byte_array, content_type=TEST_ATTACHMENT_TYPE),
        )
    )
    message_result = log_batcher.append(
        RPRequestLog(
            launch_uuid=TEST_LAUNCH_ID,
            time=helpers.timestamp(),
            message=TEST_MASSAGE,
            level=TEST_LEVEL,
            item_uuid=TEST_ITEM_ID,
        )
    )

    assert binary_result is None
    assert message_result is not None
    assert len(message_result) == 1
    assert message_result[0].file is not None
    assert log_batcher._payload_size > 0
    assert len(log_batcher._batch) == 1


def test_log_batch_triggers_previous_request_to_send():
    log_batcher = LogBatcher(entry_num=TEST_BATCH_SIZE)

    random_byte_array = bytearray(os.urandom(MAX_LOG_BATCH_PAYLOAD_SIZE))

    message_result = log_batcher.append(
        RPRequestLog(
            launch_uuid=TEST_LAUNCH_ID,
            time=helpers.timestamp(),
            message=TEST_MASSAGE,
            level=TEST_LEVEL,
            item_uuid=TEST_ITEM_ID,
        )
    )

    binary_result = log_batcher.append(
        RPRequestLog(
            launch_uuid=TEST_LAUNCH_ID,
            time=helpers.timestamp(),
            message=TEST_MASSAGE,
            level=TEST_LEVEL,
            item_uuid=TEST_ITEM_ID,
            file=RPFile(name=TEST_ATTACHMENT_NAME, content=random_byte_array, content_type=TEST_ATTACHMENT_TYPE),
        )
    )

    assert binary_result is not None
    assert message_result is None
    assert len(binary_result) == 1
    assert binary_result[0].file is None
    assert MAX_LOG_BATCH_PAYLOAD_SIZE < log_batcher._payload_size < MAX_LOG_BATCH_PAYLOAD_SIZE * 1.1
