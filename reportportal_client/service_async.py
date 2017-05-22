from logging import getLogger
import threading

from six.moves import queue

from .service import ReportPortalService

logger = getLogger(__name__)


class QueueListener(object):
    _sentinel_item = None

    def __init__(self, queue, *handlers):
        self.queue = queue
        self.handlers = handlers
        self._stop_nowait = threading.Event()
        self._stop = threading.Event()
        self._thread = None

    def dequeue(self, block=True):
        """
        Dequeue a record and return item.
        """
        return self.queue.get(block)

    def start(self):
        """
        Start the listener.
        This starts up a background thread to monitor the queue for
        items to process.
        """
        self._thread = t = threading.Thread(target=self._monitor)
        t.setDaemon(True)
        t.start()

    def prepare(self, record):
        """
        Prepare a record for handling.
        This method just returns the passed-in record. You may want to
        override this method if you need to do any custom marshalling or
        manipulation of the record before passing it to the handlers.
        """
        return record

    def handle(self, record):
        """
        Handle an item.
        This just loops through the handlers offering them the record
        to handle.
        """
        record = self.prepare(record)
        for handler in self.handlers:
            handler(record)

    def _monitor(self):
        """
        Monitor the queue for items, and ask the handler
        to deal with them.
        This method runs on a separate, internal thread.
        The thread will terminate if it sees a sentinel object in the queue.
        """
        assert (self._stop.isSet() or not self._stop_nowait.isSet(),
                ("invalid internal state _stop_nowait can not be set "
                 "if _stop is not set"))
        q = self.queue
        has_task_done = hasattr(q, 'task_done')
        while not self._stop.isSet():
            try:
                record = self.dequeue(True)
                if record is self._sentinel_item:
                    break
                self.handle(record)
                if has_task_done:
                    q.task_done()

            except queue.Empty:
                pass
        # There might still be records in the queue,
        # handle then unless _stop_nowait is set.
        while not self._stop_nowait.isSet():
            try:
                record = self.dequeue(False)
                if record is self._sentinel_item:
                    break
                self.handle(record)
                if has_task_done:
                    q.task_done()
            except queue.Empty:
                break

    def stop(self, nowait=False):
        """
        Stop the listener.
        This asks the thread to terminate, and then waits for it to do so.
        Note that if you don't call this before your application exits, there
        may be some records still left on the queue, which won't be processed.
        If nowait is False then thread will handle remaining items in queue and 
        stop.
        If nowait is True then thread will be stopped even if the queue still 
        contains items.
        """
        self._stop.set()
        if nowait:
            self._stop_nowait.set()
        self.queue.put_nowait(self._sentinel_item)
        self._thread.join()
        self._thread = None


class ReportPortalServiceAsync(object):
    BATCH_SIZE = 20
    """Wrapper around service class to transparently provide async operations 
    to agents."""

    def __init__(self, endpoint, project, token, api_base=None,
                 error_handler=None):
        """Init the service class.

        Args:
            endpoint: endpoint of report portal service.
            project: project name to use for launch names.
            token: authorization token.
            api_base: defaults to api/v1, can be changed to other version.
            error_handler: function to be called to handle errors occured during
            items processing (in thread)
        """
        super(ReportPortalServiceAsync, self).__init__()
        self.error_handler = error_handler
        self.rp_client = ReportPortalService(endpoint, project, token, api_base)
        self.listener = None
        self.queue = None
        self.log_batch = []

    def terminate(self, nowait=False):
        """
        Finalize and stop service
        :param nowait:
        :return: 
        """
        logger.debug("Terminating service")

        self.listener.stop(nowait)
        try:
            self._post_log_batch()
        except Exception as err:
            if self.error_handler:
                self.error_handler(err)
            else:
                raise

        self.queue = None
        self.listener = None

    def _post_log_batch(self):
        logger.debug("Posting log batch: {}".format(len(self.log_batch)))

        if self.log_batch:
            self.rp_client.log_batch(self.log_batch)
            self.log_batch = []

    def process_log(self, **log_item):
        """
        Special handler for log messages.
        Accumulate incoming log messages and post them in batch.
        """
        logger.debug("Processing log item: {}".format(log_item))
        self.log_batch.append(log_item)
        if len(self.log_batch) >= self.BATCH_SIZE:
            self._post_log_batch()

    def process_item(self, item):
        """
        Main item handler. Called by queue listener.
        """
        logger.debug("Processing item: {}".format(item))
        method, kwargs = item
        expected_methods = ["start_launch", "finish_launch",
                            "start_test_item", "finish_test_item", "log"]
        if method in expected_methods:
            try:
                if method == "log":
                    self.process_log(**kwargs)
                else:
                    self._post_log_batch()
                    getattr(self.rp_client, method)(**kwargs)
            except Exception as err:
                if self.error_handler:
                    if not self.error_handler(err):
                        self.terminate(nowait=True)
                else:
                    self.terminate(nowait=True)
                    raise
        else:
            raise Exception("Not expected service method: {}".format(method))

    def start_launch(self, name=None, description=None, tags=None,
                     start_time=None, mode=None):
        self.queue = queue.Queue()
        self.listener = QueueListener(self.queue, self.process_item)
        self.listener.start()
        args = {
            "name": name,
            "description": description,
            "tags": tags,
            "start_time": start_time,
            "mode": mode
        }
        self.queue.put_nowait(("start_launch", args))

    def finish_launch(self, end_time=None, status=None):
        args = {
            "end_time": end_time,
            "status": status
        }
        self.queue.put_nowait(("finish_launch", args))

    def start_test_item(self, name=None, description=None, tags=None,
                        start_time=None, type=None):
        args = {
            "name": name,
            "description": description,
            "tags": tags,
            "start_time": start_time,
            "type": type,
        }
        self.queue.put_nowait(("start_test_item", args))

    def finish_test_item(self, end_time=None, status=None, issue=None):
        args = {
            "end_time": end_time,
            "status": status,
            "issue": issue,
        }
        self.queue.put_nowait(("finish_test_item", args))

    def log(self, time=None, message=None, level=None, attachment=None):
        args = {
            "time": time,
            "message": message,
            "level": level,
            "attachment": attachment,
        }
        self.queue.put_nowait(("log", args))

