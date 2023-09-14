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

from reportportal_client.aio.tasks import (Task, BatchedTask, BatchedTaskFactory, ThreadedTask,
                                           ThreadedTaskFactory, BlockingOperationError)

DEFAULT_TASK_TIMEOUT: float = 60.0
DEFAULT_SHUTDOWN_TIMEOUT: float = 120.0
DEFAULT_TASK_TRIGGER_NUM: int = 10
DEFAULT_TASK_TRIGGER_INTERVAL: float = 1.0

__all__ = [
    'Task',
    'BatchedTask',
    'BatchedTaskFactory',
    'ThreadedTask',
    'ThreadedTaskFactory',
    'BlockingOperationError',
    'DEFAULT_TASK_TIMEOUT',
    'DEFAULT_SHUTDOWN_TIMEOUT',
    'DEFAULT_TASK_TRIGGER_NUM',
    'DEFAULT_TASK_TRIGGER_INTERVAL'
]
