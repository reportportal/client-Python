"""Worker class tests."""

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

import time

from six.moves import queue, mock

from reportportal_client.core.rp_requests import (
    HttpRequest,
    RPLogBatch,
    RPRequestLog
)
from reportportal_client.core.worker import APIWorker
from reportportal_client.helpers import timestamp

LOG_REQUEST_URL = 'http://docker.local:8080/api/v1/default_personal/log'
TEST_LAUNCH_UUID = 'test_uuid'
TEST_MASSAGE = "test message"


def test_worker_continue_working_on_request_error():
    test_queue = queue.PriorityQueue()
    worker = APIWorker(test_queue)
    worker.start()

    log_request = RPRequestLog(TEST_LAUNCH_UUID, timestamp(),
                               message=TEST_MASSAGE)
    log_batch = RPLogBatch([log_request])

    fail_session = mock.Mock()
    fail_session.side_effect = Exception()
    http_fail = HttpRequest(
        fail_session, LOG_REQUEST_URL, files=log_batch.payload,
        verify_ssl=False)
    log_batch.http_request = http_fail
    worker.send(log_batch)

    start_time = time.time()
    while fail_session.call_count < 1 and time.time() - start_time < 10:
        time.sleep(0.1)

    assert fail_session.call_count == 1
    assert log_batch.response is None

    pass_session = mock.Mock()
    http_pass = HttpRequest(
        pass_session, LOG_REQUEST_URL, files=log_batch.payload,
        verify_ssl=False)
    log_batch.http_request = http_pass
    worker.send(log_batch)

    start_time = time.time()
    while pass_session.call_count < 1 and time.time() - start_time < 10:
        time.sleep(0.1)

    assert pass_session.call_count == 1
    assert log_batch.response
    worker.stop()
