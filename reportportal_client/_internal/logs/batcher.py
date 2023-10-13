#  Copyright (c) 2023 EPAM Systems
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

"""This module contains a helper class to automate packaging separate Log entries into log batches."""

import logging
import threading
from typing import List, Optional, TypeVar, Generic, Dict, Any

from reportportal_client.core.rp_requests import RPRequestLog, AsyncRPRequestLog
from reportportal_client.logs import MAX_LOG_BATCH_SIZE, MAX_LOG_BATCH_PAYLOAD_SIZE

logger = logging.getLogger(__name__)

T_co = TypeVar('T_co', bound='RPRequestLog', covariant=True)


class LogBatcher(Generic[T_co]):
    """Log packaging class to automate compiling separate Log entries into log batches.

    The class accepts the maximum number of log entries in desired batches and maximum batch size to conform
    with maximum request size limits, configured on servers. The class implementation is thread-safe.
    """

    entry_num: int
    payload_limit: int
    _lock: threading.Lock
    _batch: List[T_co]
    _payload_size: int

    def __init__(self, entry_num=MAX_LOG_BATCH_SIZE, payload_limit=MAX_LOG_BATCH_PAYLOAD_SIZE) -> None:
        """Initialize the batcher instance with empty batch and specific limits.

        :param entry_num:     maximum numbers of entries in a Log batch
        :param payload_limit: maximum batch size in bytes
        """
        self.entry_num = entry_num
        self.payload_limit = payload_limit
        self._lock = threading.Lock()
        self._batch = []
        self._payload_size = 0

    def _append(self, size: int, log_req: T_co) -> Optional[List[T_co]]:
        with self._lock:
            if self._payload_size + size >= self.payload_limit:
                if len(self._batch) > 0:
                    batch = self._batch
                    self._batch = [log_req]
                    self._payload_size = size
                    return batch
            self._batch.append(log_req)
            self._payload_size += size
            if len(self._batch) >= self.entry_num:
                batch = self._batch
                self._batch = []
                self._payload_size = 0
                return batch

    def append(self, log_req: RPRequestLog) -> Optional[List[RPRequestLog]]:
        """Add a log request object to internal batch and return the batch if it's full.

        :param   log_req: log request object
        :return: a batch or None
        """
        return self._append(log_req.multipart_size, log_req)

    async def append_async(self, log_req: AsyncRPRequestLog) -> Optional[List[AsyncRPRequestLog]]:
        """Add a log request object to internal batch and return the batch if it's full.

        :param   log_req: log request object
        :return: a batch or None
        """
        return self._append(await log_req.multipart_size, log_req)

    def flush(self) -> Optional[List[T_co]]:
        """Immediately return everything what's left in the internal batch.

        :return: a batch or None
        """
        with self._lock:
            if len(self._batch) > 0:
                batch = self._batch
                self._batch = []
                self._payload_size = 0
                return batch

    def __getstate__(self) -> Dict[str, Any]:
        """Control object pickling and return object fields as Dictionary.

        :return: object state dictionary
        :rtype: dict
        """
        state = self.__dict__.copy()
        # Don't pickle 'session' field, since it contains unpickling 'socket'
        del state['_lock']
        return state

    def __setstate__(self, state: Dict[str, Any]) -> None:
        """Control object pickling, receives object state as Dictionary.

        :param dict state: object state dictionary
        """
        self.__dict__.update(state)
        self._lock = threading.Lock()
