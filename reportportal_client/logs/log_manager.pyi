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

from logging import Logger
from threading import Lock
from typing import Dict, List, Optional, Text

from requests import Session
from six.moves import queue

from reportportal_client.core.rp_requests import (
    RPRequestLog as RPRequestLog
)
from reportportal_client.core.worker import APIWorker as APIWorker

logger: Logger

MAX_LOG_BATCH_PAYLOAD_SIZE: int


class LogManager:
    _lock: Lock = ...
    _log_endpoint: Text = ...
    _batch: List = ...
    _payload_size: int = ...
    _worker: Optional[APIWorker] = ...
    api_version: Text = ...
    queue: queue.PriorityQueue = ...
    launch_id: Text = ...
    max_entry_number: int = ...
    project_name: Text = ...
    rp_url: Text = ...
    session: Session = ...
    verify_ssl: bool = ...
    max_payload_size: int = ...

    def __init__(self,
                 rp_url: Text,
                 session: Session,
                 api_version: Text,
                 launch_id: Text,
                 project_name: Text,
                 max_entry_number: int = ...,
                 verify_ssl: bool = ...,
                 max_payload_size: int = ...) -> None: ...

    def _log_process(self, log_req: RPRequestLog) -> None: ...

    def _send_batch(self) -> None: ...

    def log(self,
            time: Text,
            message: Optional[Text] = ...,
            level: Optional[Text] = ...,
            attachment: Optional[Dict] = ...,
            item_id: Optional[Text] = ...) -> None: ...

    def start(self) -> None: ...

    def stop(self) -> None: ...

    def stop_force(self) -> None: ...