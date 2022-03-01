"""This module contains worker that makes non-blocking HTTP requests.

Copyright (c) 2018 https://reportportal.io .

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

https://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import logging
from threading import currentThread, Thread

from aenum import auto, Enum, unique
from six.moves import queue

from reportportal_client.static.defines import Priority

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


@unique
class ControlCommand(Enum):
    """This class stores worker control commands."""

    CLEAR_QUEUE = auto()
    NOP = auto()
    REPORT_STATUS = auto()
    STOP = auto()
    STOP_IMMEDIATE = auto()

    def is_stop_cmd(self):
        """Verify if the command is the stop one."""
        return self in (ControlCommand.STOP, ControlCommand.STOP_IMMEDIATE)

    @property
    def priority(self):
        if self is ControlCommand.STOP_IMMEDIATE:
            return Priority.PRIORITY_IMMEDIATE
        else:
            return Priority.PRIORITY_MEDIUM

    def __lt__(self, other):
        """Priority protocol for the PriorityQueue."""
        return self.priority < other.priority


class APIWorker(object):
    """Worker that makes HTTP requests to the Report Portal."""

    def __init__(self, task_queue):
        """Initialize instance attributes."""
        self._queue = task_queue
        self._thread = None
        self.name = self.__class__.__name__

    def _command_get(self):
        """Get command from the queue."""
        try:
            cmd = self._queue.get(timeout=0.1)
            return cmd
        except queue.Empty:
            return None

    def _command_process(self, cmd):
        """Process control command sent to the worker.

        :param cmd: a command to be processed
        """
        if not cmd:
            return  # No command received

        logger.debug('[%s] Processing {%s} command', self.name, cmd)
        if cmd == ControlCommand.REPORT_STATUS:
            logger.debug('[%s] Current status for tasks is: {%s} unfinished',
                         self.name, self._queue.unfinished_tasks)

        if cmd.is_stop_cmd():
            if cmd == ControlCommand.STOP_IMMEDIATE:
                self._stop_immediately()
            else:
                self._stop()

    def _monitor(self):
        """Monitor worker queues and process them.

        This method runs on a separate, internal thread. The thread will
        terminate if the stop_immediate control command is received. If
        the stop control command is sent, the worker will process all the
        items from the queue before terminate.
        """
        while True:
            cmd = self._command_get()

            if isinstance(cmd, ControlCommand):
                logger.debug('[%s] Received {%s} command', self.name, cmd)
                self._command_process(cmd)
                if cmd and cmd.is_stop_cmd():
                    logger.debug('[%s] Exiting due to {%s} command',
                                 self.name, cmd)
                    break
            else:
                logger.debug('[%s] Received {%s} request', self.name, cmd)
                self._request_process(cmd)

    def _request_process(self, request):
        """Send request to RP and update response attribute of the request."""
        if not request:
            return  # No request received

        logger.debug('[%s] Processing {%s} request', self.name, request)
        try:
            request.response = request.http_request.make()
        except Exception as err:
            logger.error('[%s] Unknown exception has occurred. Terminating the'
                         'worker.')
            logger.error(str(err))
            self.stop_immediate()
        self._queue.task_done()

    def _stop(self):
        """Routine that stops the worker thread(s).

        This method process everything in worker's queue first, ignoring
        commands and terminates thread only after.
        """
        request = self._command_get()
        while request is not None:
            if not isinstance(request, ControlCommand):
                self._request_process(request)
            request = self._command_get()
        self._stop_immediately()

    def _stop_immediately(self):
        """Routine that stops the worker thread(s) immediately.

        This asks the thread to terminate, and then waits for it to do so.
        Note that if you don't call this before your application exits, there
        may be some records still left on the queue, which won't be processed.
        """
        if self._thread.is_alive() and self._thread is not currentThread():
            self._thread.join()
        self._thread = None

    def is_alive(self):
        """Check whether the current worker is alive or not.

        :return: True is self._thread is not None, False otherwise
        """
        return bool(self._thread)

    def _put(self, priority, cmd):
        """Put a command into the queue with specified priority.

        :param priority: processing priority
        :param cmd:      a command to be processed
        """
        self._queue.put((priority, cmd))

    def send(self, entity):
        """Send control command or a request to the worker queue."""
        self._queue.put(entity)

    def start(self):
        """Start the worker.

        This starts up a background thread to monitor the queue for
        requests to process.
        """
        self._thread = Thread(target=self._monitor)
        self._thread.setDaemon(True)
        self._thread.start()

    def stop(self):
        """Stop the worker.

        Send the appropriate control command to the worker.
        """
        self.send(ControlCommand.STOP)

    def stop_immediate(self):
        """Stop the worker immediately.

        Send the appropriate control command to the worker.
        """
        self.send(ControlCommand.STOP_IMMEDIATE)
