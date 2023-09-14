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
import logging
import threading
from typing import List, Optional, TypeVar, Generic

from reportportal_client import helpers
from reportportal_client.core.rp_requests import RPRequestLog, AsyncRPRequestLog
from reportportal_client.logs import MAX_LOG_BATCH_SIZE, MAX_LOG_BATCH_PAYLOAD_SIZE

logger = logging.getLogger(__name__)

T_co = TypeVar('T_co', bound='RPRequestLog', covariant=True)


class LogBatcher(Generic[T_co]):
    entry_num: int
    payload_limit: int
    _lock: threading.Lock
    _batch: List[T_co]
    _payload_size: int

    def __init__(self, entry_num=MAX_LOG_BATCH_SIZE, payload_limit=MAX_LOG_BATCH_PAYLOAD_SIZE):
        self.entry_num = entry_num
        self.payload_limit = payload_limit
        self._lock = threading.Lock()
        self._batch = []
        self._payload_size = helpers.TYPICAL_MULTIPART_FOOTER_LENGTH

    def _append(self, size: int, log_req: T_co) -> Optional[List[T_co]]:
        with self._lock:
            if self._payload_size + size >= self.payload_limit:
                if len(self._batch) > 0:
                    batch = self._batch
                    self._batch = [log_req]
                    self._payload_size = helpers.TYPICAL_MULTIPART_FOOTER_LENGTH
                    return batch
            self._batch.append(log_req)
            self._payload_size += size
            if len(self._batch) >= self.entry_num:
                batch = self._batch
                self._batch = []
                self._payload_size = helpers.TYPICAL_MULTIPART_FOOTER_LENGTH
                return batch

    def append(self, log_req: RPRequestLog) -> Optional[List[RPRequestLog]]:
        """Add a log request object to internal batch and return the batch if it's full.

        :param  log_req: log request object
        :return ready to send batch or None
        """
        return self._append(log_req.multipart_size, log_req)

    async def append_async(self, log_req: AsyncRPRequestLog) -> Optional[List[AsyncRPRequestLog]]:
        """Add a log request object to internal batch and return the batch if it's full.

        :param  log_req: log request object
        :return ready to send batch or None
        """
        return self._append(await log_req.multipart_size, log_req)

    def flush(self) -> Optional[List[T_co]]:
        with self._lock:
            if len(self._batch) > 0:
                batch = self._batch
                self._batch = []
                return batch
