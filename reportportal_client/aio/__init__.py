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

"""Common package for Asynchronous I/O clients and utilities."""

from reportportal_client.aio.client import (
    DEFAULT_SHUTDOWN_TIMEOUT,
    DEFAULT_TASK_TIMEOUT,
    DEFAULT_TASK_TRIGGER_INTERVAL,
    DEFAULT_TASK_TRIGGER_NUM,
    AsyncRPClient,
    BatchedRPClient,
    ThreadedRPClient,
)
from reportportal_client.aio.tasks import BlockingOperationError, Task

__all__ = [
    "Task",
    "BlockingOperationError",
    "DEFAULT_TASK_TIMEOUT",
    "DEFAULT_SHUTDOWN_TIMEOUT",
    "DEFAULT_TASK_TRIGGER_NUM",
    "DEFAULT_TASK_TRIGGER_INTERVAL",
    "AsyncRPClient",
    "BatchedRPClient",
    "ThreadedRPClient",
]
