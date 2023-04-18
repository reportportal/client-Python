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
"""Report portal logging handling module."""

import logging
import sys

from six import PY2
from six.moves.urllib.parse import urlparse

# noinspection PyProtectedMember
from reportportal_client._local import current
from reportportal_client.helpers import timestamp


class RPLogger(logging.getLoggerClass()):
    """RPLogger class for low-level logging in tests."""

    def __init__(self, name, level=0):
        """
        Initialize RPLogger instance.

        :param name:  logger name
        :param level: level of logs
        """
        super(RPLogger, self).__init__(name, level=level)

    def _log(self, level, msg, args, exc_info=None, extra=None,
             stack_info=False, attachment=None, **kwargs):
        """
        Low-level logging routine which creates a LogRecord and then calls.

        all the handlers of this logger to handle the record
        :param level:      level of log
        :param msg:        message in log body
        :param args:       additional args
        :param exc_info:   system exclusion info
        :param extra:      extra info
        :param stack_info: stacktrace info
        :param attachment: attachment file
        """
        sinfo = None
        if logging._srcfile:
            # IronPython doesn't track Python frames, so findCaller raises an
            # exception on some versions of IronPython. We trap it here so that
            # IronPython can use logging.
            try:
                if PY2:
                    # In python2.7 findCaller() don't accept any parameters
                    # and returns 3 elements
                    fn, lno, func = self.findCaller()
                else:
                    if 'stacklevel' in kwargs:
                        fn, lno, func, sinfo = \
                            self.findCaller(stack_info, kwargs['stacklevel'])
                    else:
                        fn, lno, func, sinfo = self.findCaller(stack_info)

            except ValueError:  # pragma: no cover
                fn, lno, func = '(unknown file)', 0, '(unknown function)'
        else:
            fn, lno, func = '(unknown file)', 0, '(unknown function)'

        if exc_info and not isinstance(exc_info, tuple):
            exc_info = sys.exc_info()

        if PY2:
            # In python2.7 makeRecord() accepts everything but sinfo
            record = self.makeRecord(self.name, level, fn, lno, msg, args,
                                     exc_info, func, extra)
        else:
            record = self.makeRecord(self.name, level, fn, lno, msg, args,
                                     exc_info, func, extra, sinfo)

        if not getattr(record, 'attachment', None):
            record.attachment = attachment
        self.handle(record)


class RPLogHandler(logging.Handler):
    """RPLogHandler class for logging tests."""

    # Map loglevel codes from `logging` module to ReportPortal text names:
    _loglevel_map = {
        logging.NOTSET: 'TRACE',
        logging.DEBUG: 'DEBUG',
        logging.INFO: 'INFO',
        logging.WARNING: 'WARN',
        logging.ERROR: 'ERROR',
        logging.CRITICAL: 'ERROR',
    }
    _sorted_levelnos = sorted(_loglevel_map.keys(), reverse=True)

    def __init__(self, level=logging.NOTSET, filter_client_logs=False,
                 endpoint=None,
                 ignored_record_names=tuple('reportportal_client'),
                 rp_client=None):
        """
        Initialize RPLogHandler instance.

        :param level:                level of logging
        :param filter_client_logs:   if True throw away logs emitted by a
        ReportPortal client
        :param endpoint:             Report Portal endpoint URL, used to filter
        out urllib3 logs, mutes Report Portal HTTP logs if set, optional
        parameter
        :param ignored_record_names: a tuple of record names which will be
        filtered out by the handler (with startswith method)
        """
        super(RPLogHandler, self).__init__(level)
        self.filter_client_logs = filter_client_logs
        self.ignored_record_names = ignored_record_names
        self.endpoint = endpoint
        self.rp_client = rp_client

    def filter(self, record):
        """Filter specific records to avoid sending those to RP.

        :param record: A log record to be filtered
        :return:       False if the given record does no fit for sending
                       to RP, otherwise True.
        """
        if not self.filter_client_logs:
            return True
        if record.name.startswith(self.ignored_record_names):
            return False
        if record.name.startswith('urllib3.connectionpool'):
            # Filter the reportportal_client requests instance
            # urllib3 usage
            hostname = urlparse(self.endpoint).hostname
            if hostname:
                if hasattr(hostname, 'decode') and callable(hostname.decode):
                    if hostname.decode('utf-8') in self.format(record):
                        return False
                else:
                    if str(hostname) in self.format(record):
                        return False
        return True

    def _get_rp_log_level(self, levelno):
        return next(
            (
                self._loglevel_map[level]
                for level in self._sorted_levelnos
                if levelno >= level
            ),
            self._loglevel_map[logging.NOTSET],
        )

    def emit(self, record):
        """
        Emit function.

        :param record: a log Record of requests
        """
        msg = ''

        # noinspection PyBroadException
        try:
            msg = self.format(record)
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception:
            self.handleError(record)

        log_level = self._get_rp_log_level(record.levelno)
        rp_client = self.rp_client
        if not rp_client:
            rp_client = current()
        if rp_client:
            rp_client.log(
                timestamp(),
                msg,
                level=log_level,
                attachment=record.__dict__.get('attachment', None),
                item_id=rp_client.current_item()
            )
        return
