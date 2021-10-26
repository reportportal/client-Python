"""This module contains management functionality for processing logs.

Copyright (c) 2018 http://reportportal.io .
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at
http://www.apache.org/licenses/LICENSE-2.0
Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import logging
from threading import Lock
from time import sleep

from six.moves import queue

from reportportal_client.core.rp_requests import (
    HttpRequest,
    RPFile,
    RPLogBatch,
    RPRequestLog
)
from reportportal_client.core.worker import APIWorker


logger = logging.getLogger(__name__)


class LogManager(object):
    """Manager of the log items."""

    def __init__(self, rp_url, session, api_version, launch_id, project_name,
                 log_batch_size=20, verify_ssl=True):
        """Initialize instance attributes.

        :param rp_url:         Report portal URL
        :param session:        HTTP Session object
        :param api_version:    RP API version
        :param launch_id:      Parent launch UUID
        :param project_name:   RP project name
        :param log_batch_size: The amount of log objects that need to be
                               gathered before processing
        :param verify_ssl:     Indicates that it is necessary to verify SSL
                               certificates within HTTP request
        """
        self._lock = Lock()
        self._logs_batch = []
        self._worker = None
        self.api_version = api_version
        self.command_queue = queue.Queue()
        self.data_queue = queue.PriorityQueue()
        self.launch_id = launch_id
        self.log_batch_size = log_batch_size
        self.project_name = project_name
        self.rp_url = rp_url
        self.session = session
        self.verify_ssl = verify_ssl

        self._log_endpoint = (
            '{rp_url}/api/{version}/{project_name}/log'
            .format(rp_url=rp_url, version=self.api_version,
                    project_name=self.project_name))

    def _log_process(self, log_req):
        """Process the given log request.

        :param log_req: RPRequestLog object
        """
        self._logs_batch.append(log_req)
        if len(self._logs_batch) >= self.log_batch_size:
            self._send_batch()

    def _send_batch(self):
        """Send existing batch logs to the worker."""
        batch = RPLogBatch(self._logs_batch)
        http_request = HttpRequest(
            self.session.post, self._log_endpoint, files=batch.payload,
            verify_ssl=self.verify_ssl)
        batch.http_request = http_request
        self._worker.send_request(batch)
        self._logs_batch.clear()

    def log(self, time, message=None, level=None, attachment=None,
            item_id=None):
        """Log message. Can be added to test item in any state.

        :param time:        Log time
        :param message:     Log message
        :param level:       Log level
        :param attachment:  Attachments(images,files,etc.)
        :param item_id:     parent item UUID
        """
        rp_file = RPFile(**attachment) if attachment else None
        rp_log = RPRequestLog(self.launch_id, time, rp_file, item_id,
                              level, message)
        self._log_process(rp_log)

    def start(self):
        """Create a new instance of the Worker class and start it."""
        if not self._worker:
            self._worker = APIWorker(self.command_queue, self.data_queue)
            self._worker.start()

    def stop(self):
        """Send last batches to the worker followed by the stop command."""
        if self._worker:
            with self._lock:
                if self._logs_batch:
                    self._send_batch()
                self._worker.stop()
                logger.debug('Waiting for worker {0} to complete'
                             'processing batches.'.format(self._worker))
                while self._worker.is_alive():
                    sleep(0.1)

    def stop_force(self):
        """Send stop immediate command to the worker."""
        if self._worker:
            self._worker.stop_immediate()
