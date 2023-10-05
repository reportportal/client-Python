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

"""This module contains management functionality for processing logs."""

import logging
import queue
import warnings
from threading import Lock

from reportportal_client import helpers
# noinspection PyProtectedMember
from reportportal_client._internal.static.defines import NOT_FOUND
from reportportal_client.core.rp_requests import (
    HttpRequest,
    RPFile,
    RPLogBatch,
    RPRequestLog
)
from reportportal_client.core.worker import APIWorker
from reportportal_client.logs import MAX_LOG_BATCH_SIZE, MAX_LOG_BATCH_PAYLOAD_SIZE

logger = logging.getLogger(__name__)


class LogManager:
    """Manager of the log items."""

    def __init__(self, rp_url, session, api_version, launch_id, project_name,
                 max_entry_number=MAX_LOG_BATCH_SIZE, verify_ssl=True,
                 max_payload_size=MAX_LOG_BATCH_PAYLOAD_SIZE):
        """Initialize instance attributes.

        :param rp_url:           ReportPortal URL
        :param session:          HTTP Session object
        :param api_version:      RP API version
        :param launch_id:        Parent launch UUID
        :param project_name:     RP project name
        :param max_entry_number: The amount of log objects that need to be
                                 gathered before processing
        :param verify_ssl:       Indicates that it is necessary to verify SSL
                                 certificates within HTTP request
        :param max_payload_size: maximum size in bytes of logs that can be
                                 processed in one batch
        """
        warnings.warn(
            message='`LogManager` class is deprecated since 5.5.0 and will be subject for removing in the'
                    ' next major version.',
            category=DeprecationWarning,
            stacklevel=2
        )
        self._lock = Lock()
        self._batch = []
        self._payload_size = helpers.TYPICAL_MULTIPART_FOOTER_LENGTH
        self._worker = None
        self.api_version = api_version
        self.queue = queue.PriorityQueue()
        self.launch_id = launch_id
        self.max_entry_number = max_entry_number
        self.max_payload_size = max_payload_size
        self.project_name = project_name
        self.rp_url = rp_url
        self.session = session
        self.verify_ssl = verify_ssl

        self._log_endpoint = (
            '{rp_url}/api/{version}/{project_name}/log'
            .format(rp_url=rp_url.rstrip('/'), version=self.api_version,
                    project_name=self.project_name))

    def _send_batch(self):
        """Send existing batch logs to the worker."""
        batch = RPLogBatch(self._batch)
        http_request = HttpRequest(
            self.session.post, self._log_endpoint, files=batch.payload,
            verify_ssl=self.verify_ssl)
        self._worker.send(http_request)
        self._batch = []
        self._payload_size = helpers.TYPICAL_MULTIPART_FOOTER_LENGTH

    def _log_process(self, log_req):
        """Process the given log request.

        :param log_req: RPRequestLog object
        """
        rq_size = log_req.multipart_size
        with self._lock:
            if self._payload_size + rq_size >= self.max_payload_size:
                if len(self._batch) > 0:
                    self._send_batch()
            self._batch.append(log_req)
            self._payload_size += rq_size
            if len(self._batch) >= self.max_entry_number:
                self._send_batch()

    def log(self, time, message=None, level=None, attachment=None,
            item_id=None):
        """Log message. Can be added to test item in any state.

        :param time:        Log time
        :param message:     Log message
        :param level:       Log level
        :param attachment:  Attachments(images,files,etc.)
        :param item_id:     parent item UUID
        """
        if item_id is NOT_FOUND:
            logger.warning("Attempt to log to non-existent item")
            return
        rp_file = RPFile(**attachment) if attachment else None
        rp_log = RPRequestLog(self.launch_id, time, rp_file, item_id,
                              level, message)
        self._log_process(rp_log)

    def start(self):
        """Create a new instance of the Worker class and start it."""
        if not self._worker:
            # the worker might be already created in case of deserialization
            self._worker = APIWorker(self.queue)
        self._worker.start()

    def stop(self):
        """Send last batches to the worker followed by the stop command."""
        if self._worker:
            with self._lock:
                if self._batch:
                    self._send_batch()
                logger.debug('Waiting for worker {0} to complete'
                             'processing batches.'.format(self._worker))
                self._worker.stop()

    def stop_force(self):
        """Send stop immediate command to the worker."""
        if self._worker:
            self._worker.stop_immediate()
