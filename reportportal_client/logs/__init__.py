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

"""ReportPortal logging handling module."""

import logging
import sys
import threading
from typing import TYPE_CHECKING, Any, Optional, Union
from urllib.parse import urlparse

# noinspection PyProtectedMember
from reportportal_client._internal.local import current, set_current
from reportportal_client.helpers import TYPICAL_MULTIPART_FOOTER_LENGTH, timestamp

if TYPE_CHECKING:
    from reportportal_client.client import RP

LOG_LEVEL_MAPPING: dict[int, str] = {
    logging.NOTSET: "TRACE",
    logging.DEBUG: "DEBUG",
    logging.INFO: "INFO",
    logging.WARNING: "WARN",
    logging.ERROR: "ERROR",
    logging.CRITICAL: "ERROR",
}

MAX_LOG_BATCH_SIZE: int = 20
MAX_LOG_BATCH_PAYLOAD_SIZE: int = int((64 * 1024 * 1024) * 0.98) - TYPICAL_MULTIPART_FOOTER_LENGTH


class RPLogger(logging.getLoggerClass()):  # type: ignore
    """RPLogger class for low-level logging in tests."""

    def __init__(self, name: str, level: int = 0) -> None:
        """
        Initialize RPLogger instance.

        :param name:  logger name
        :param level: level of logs
        """
        super(RPLogger, self).__init__(name, level=level)

    def _log(
        self,
        level: int,
        msg: Any,
        args: tuple,
        exc_info: Optional[Union[bool, tuple]] = None,
        extra: Optional[dict] = None,
        stack_info: bool = False,
        attachment: Optional[dict] = None,
        **kwargs: Any,
    ) -> None:
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
                if sys.version_info >= (3, 11):
                    kwargs.setdefault("stacklevel", 2)
                if "stacklevel" in kwargs:
                    fn, lno, func, sinfo = self.findCaller(stack_info, kwargs["stacklevel"])
                else:
                    fn, lno, func, sinfo = self.findCaller(stack_info)

            except ValueError:  # pragma: no cover
                fn, lno, func = "(unknown file)", 0, "(unknown function)"
        else:
            fn, lno, func = "(unknown file)", 0, "(unknown function)"

        if exc_info and not isinstance(exc_info, tuple):
            exc_info = sys.exc_info()

        record = self.makeRecord(self.name, level, fn, lno, msg, args, exc_info, func, extra, sinfo)
        if not getattr(record, "attachment", None):
            record.attachment = attachment
        self.handle(record)


class RPLogHandler(logging.Handler):
    """RPLogHandler class for logging tests."""

    # Map loglevel codes from `logging` module to ReportPortal text names:
    _loglevel_map: dict[int, str]
    _sorted_levelnos: list[int]
    filter_client_logs: bool
    ignored_record_names: tuple[str, ...]
    endpoint: Optional[str]
    rp_client: Optional["RP"]

    def __init__(
        self,
        level: int = logging.NOTSET,
        filter_client_logs: bool = False,
        endpoint: Optional[str] = None,
        ignored_record_names: tuple = tuple("reportportal_client"),
        rp_client: Optional["RP"] = None,
        custom_levels: Optional[dict[int, str]] = None,
    ) -> None:
        """
        Initialize RPLogHandler instance.

        :param level:                level of logging
        :param filter_client_logs:   if True throw away logs emitted by a
                                     ReportPortal client
        :param endpoint:             ReportPortal endpoint URL, used to filter out urllib3 logs, mutes
                                     ReportPortal HTTP logs if set, optional parameter
        :param ignored_record_names: a tuple of record names which will be filtered out by the handler
                                     (with startswith method)
        """
        super(RPLogHandler, self).__init__(level)
        self._loglevel_map = LOG_LEVEL_MAPPING.copy()
        if custom_levels:
            self._loglevel_map.update(custom_levels)
        self._sorted_levelnos = sorted(self._loglevel_map.keys(), reverse=True)
        self.filter_client_logs = filter_client_logs
        self.ignored_record_names = ignored_record_names
        self.endpoint = endpoint
        self.rp_client = rp_client

    def filter(self, record: logging.LogRecord) -> bool:
        """Filter specific records to avoid sending those to RP.

        :param record: A log record to be filtered
        :return:       False if the given record does no fit for sending
                       to RP, otherwise True.
        """
        if not self.filter_client_logs:
            return True
        if record.name.startswith(self.ignored_record_names):
            return False
        if record.name.startswith("urllib3.connectionpool"):
            # Filter the reportportal_client requests instance
            # urllib3 usage
            if self.endpoint:
                hostname = urlparse(self.endpoint).hostname
                if hostname:
                    if hostname in self.format(record):
                        return False
        return True

    def _get_rp_log_level(self, levelno: int) -> str:
        return next(
            (self._loglevel_map[level] for level in self._sorted_levelnos if levelno >= level),
            self._loglevel_map[logging.NOTSET],
        )

    def emit(self, record: logging.LogRecord) -> None:
        """
        Emit function.

        :param record: a log Record of requests
        """
        msg = ""

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
            if not rp_client:
                rp_client = getattr(threading.current_thread(), "parent_rp_client", None)
                if rp_client:
                    set_current(rp_client)
        if rp_client:
            rp_client.log(
                timestamp(),
                msg,
                level=log_level,
                attachment=record.__dict__.get("attachment", None),
                item_id=rp_client.current_item(),
            )
        return
