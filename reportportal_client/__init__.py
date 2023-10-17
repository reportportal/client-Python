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

"""This package is the base package for ReportPortal client."""
import typing
import warnings

import aenum

# noinspection PyProtectedMember
from reportportal_client._internal.local import current, set_current
from reportportal_client.aio.client import AsyncRPClient, BatchedRPClient, ThreadedRPClient
from reportportal_client.client import RP, RPClient, OutputType
from reportportal_client.logs import RPLogger, RPLogHandler
from reportportal_client.steps import step


class ClientType(aenum.Enum):
    """Enum of possible type of ReportPortal clients."""

    SYNC = aenum.auto()
    ASYNC = aenum.auto()
    ASYNC_THREAD = aenum.auto()
    ASYNC_BATCHED = aenum.auto()


# noinspection PyIncorrectDocstring
def create_client(
        client_type: ClientType,
        endpoint: str,
        project: str,
        *,
        api_key: str = None,
        **kwargs: typing.Any
) -> typing.Optional[RP]:
    """Create and ReportPortal Client based on the type and arguments provided.

    :param client_type:             Type of the Client to create.
    :type client_type:              ClientType
    :param endpoint:                Endpoint of the ReportPortal service.
    :type endpoint:                 str
    :param project:                 Project name to report to.
    :type project:                  str
    :param api_key:                 Authorization API key.
    :type api_key:                  str
    :param launch_uuid:             A launch UUID to use instead of starting own one.
    :type launch_uuid:              str
    :param is_skipped_an_issue:     Option to mark skipped tests as not 'To Investigate' items on the server
                                    side.
    :type is_skipped_an_issue:      bool
    :param verify_ssl:              Option to skip ssl verification.
    :type verify_ssl:               typing.Union[bool, str]
    :param retries:                 Number of retry attempts to make in case of connection / server
                                    errors.
    :type retries:                  int
    :param max_pool_size:           Option to set the maximum number of connections to save the pool.
    :type max_pool_size:            int
    :param http_timeout :           A float in seconds for connect and read timeout. Use a Tuple to
                                    specific connect and read separately.
    :type http_timeout:             Tuple[float, float]
    :param mode:                    Launch mode, all Launches started by the client will be in that mode.
    :type mode:                     str
    :param launch_uuid_print:       Print Launch UUID into passed TextIO or by default to stdout.
    :type launch_uuid_print:        bool
    :param print_output:            Set output stream for Launch UUID printing.
    :type print_output:             OutputType
    :param truncate_attributes:     Truncate test item attributes to default maximum length.
    :type truncate_attributes:      bool
    :param log_batch_size:          Option to set the maximum number of logs that can be processed in one
                                    batch.
    :type log_batch_size:           int
    :param log_batch_payload_limit: Maximum size in bytes of logs that can be processed in one batch.
    :type log_batch_payload_limit:  int
    :param keepalive_timeout:       For Async Clients only. Maximum amount of idle time in seconds before
                                    force connection closing.
    :type keepalive_timeout:        int
    :param task_timeout:            For Async Threaded and Batched Clients only. Time limit in seconds for a
                                    Task processing.
    :type task_timeout:             float
    :param shutdown_timeout:        For Async Threaded and Batched Clients only. Time limit in seconds for
                                    shutting down internal Tasks.
    :type shutdown_timeout:         float
    :param trigger_num:             For Async Batched Client only. Number of tasks which triggers Task batch
                                    execution.
    :type trigger_num:              int
    :param trigger_interval:        For Async Batched Client only. Time limit which triggers Task batch
                                    execution.
    :type trigger_interval:         float
    :return: ReportPortal Client instance.
    """
    if client_type is ClientType.SYNC:
        return RPClient(endpoint, project, api_key=api_key, **kwargs)
    if client_type is ClientType.ASYNC:
        return AsyncRPClient(endpoint, project, api_key=api_key, **kwargs)
    if client_type is ClientType.ASYNC_THREAD:
        return ThreadedRPClient(endpoint, project, api_key=api_key, **kwargs)
    if client_type is ClientType.ASYNC_BATCHED:
        return BatchedRPClient(endpoint, project, api_key=api_key, **kwargs)
    warnings.warn(f'Unknown ReportPortal Client type requested: {client_type}', RuntimeWarning, stacklevel=2)


__all__ = [
    'ClientType',
    'create_client',
    'current',
    'set_current',
    'RP',
    'RPClient',
    'AsyncRPClient',
    'BatchedRPClient',
    'ThreadedRPClient',
    'OutputType',
    'RPLogger',
    'RPLogHandler',
    'step',
]
