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

import sys
import warnings
from typing import Optional, Tuple, TypedDict, Union

# noinspection PyUnreachableCode
if sys.version_info >= (3, 11):
    from typing import Unpack
else:
    from typing_extensions import Unpack

import aenum

# noinspection PyProtectedMember
from reportportal_client._internal.local import current, set_current
from reportportal_client.aio.client import AsyncRPClient, BatchedRPClient, ThreadedRPClient
from reportportal_client.client import RP, OutputType, RPClient
from reportportal_client.logs import RPLogger, RPLogHandler
from reportportal_client.steps import step


class ClientType(aenum.Enum):
    """Enum of possible type of ReportPortal clients."""

    SYNC = aenum.auto()
    ASYNC = aenum.auto()
    ASYNC_THREAD = aenum.auto()
    ASYNC_BATCHED = aenum.auto()


class _ClientOptions(TypedDict, total=False):
    client_type: ClientType
    endpoint: str
    project: str
    api_key: Optional[str]
    # OAuth 2.0 parameters
    oauth_uri: Optional[str]
    oauth_username: Optional[str]
    oauth_password: Optional[str]
    oauth_client_id: Optional[str]
    oauth_client_secret: Optional[str]
    oauth_scope: Optional[str]
    # Common client parameters
    launch_uuid: Optional[str]
    is_skipped_an_issue: bool
    verify_ssl: Union[bool, str]
    retries: int
    max_pool_size: int
    http_timeout: Union[float, Tuple[float, float]]
    mode: str
    launch_uuid_print: bool
    print_output: OutputType
    truncate_attributes: bool
    log_batch_size: int
    log_batch_payload_limit: int
    # Async client specific parameters
    keepalive_timeout: float
    # Async threaded/batched client specific parameters
    task_timeout: float
    shutdown_timeout: float
    # Async batched client specific parameters
    trigger_num: int
    trigger_interval: float


# noinspection PyIncorrectDocstring
def create_client(
    client_type: ClientType, endpoint: str, project: str, **kwargs: Unpack[_ClientOptions]
) -> Optional[RP]:
    """Create and ReportPortal Client based on the type and arguments provided.

    :param client_type:             Type of the Client to create.
    :param endpoint:                Endpoint of the ReportPortal service.
    :param project:                 Project name to report to.
    :param api_key:                 Authorization API key.
    :param oauth_uri:               OAuth 2.0 token endpoint URI (for OAuth authentication).
    :param oauth_username:          Username for OAuth 2.0 authentication.
    :param oauth_password:          Password for OAuth 2.0 authentication.
    :param oauth_client_id:         OAuth 2.0 client ID.
    :param oauth_client_secret:     OAuth 2.0 client secret (optional).
    :param oauth_scope:             OAuth 2.0 scope (optional).
    :param launch_uuid:             A launch UUID to use instead of starting own one.
    :param is_skipped_an_issue:     Option to mark skipped tests as not 'To Investigate' items on the server
                                    side.
    :param verify_ssl:              Option to skip ssl verification.
    :param retries:                 Number of retry attempts to make in case of connection / server
                                    errors.
    :param max_pool_size:           Option to set the maximum number of connections to save the pool.
    :param http_timeout :           A float in seconds for connect and read timeout. Use a Tuple to
                                    specific connect and read separately.
    :param mode:                    Launch mode, all Launches started by the client will be in that mode.
    :param launch_uuid_print:       Print Launch UUID into passed TextIO or by default to stdout.
    :param print_output:            Set output stream for Launch UUID printing.
    :param truncate_attributes:     Truncate test item attributes to default maximum length.
    :param log_batch_size:          Option to set the maximum number of logs that can be processed in one
                                    batch.
    :param log_batch_payload_limit: Maximum size in bytes of logs that can be processed in one batch.
    :param keepalive_timeout:       For Async Clients only. Maximum amount of idle time in seconds before
                                    force connection closing.
    :param task_timeout:            For Async Threaded and Batched Clients only. Time limit in seconds for a
                                    Task processing.
    :param shutdown_timeout:        For Async Threaded and Batched Clients only. Time limit in seconds for
                                    shutting down internal Tasks.
    :param trigger_num:             For Async Batched Client only. Number of tasks which triggers Task batch
                                    execution.
    :param trigger_interval:        For Async Batched Client only. Time limit which triggers Task batch
                                    execution.
    :return: ReportPortal Client instance.
    """
    my_kwargs = kwargs.copy()
    if "log_batch_payload_size" in my_kwargs:
        warnings.warn(
            message="Your agent is using `log_batch_payload_size` property which was introduced by mistake. "
            "The real property name is `log_batch_payload_limit`. Please consider Agent version update.",
            category=DeprecationWarning,
            stacklevel=2,
        )
        if "log_batch_payload_limit" not in my_kwargs:
            my_kwargs["log_batch_payload_limit"] = my_kwargs.pop("log_batch_payload_size")

    if client_type is ClientType.SYNC:
        return RPClient(endpoint, project, **my_kwargs)
    if client_type is ClientType.ASYNC:
        return AsyncRPClient(endpoint, project, **my_kwargs)
    if client_type is ClientType.ASYNC_THREAD:
        return ThreadedRPClient(endpoint, project, **my_kwargs)
    if client_type is ClientType.ASYNC_BATCHED:
        return BatchedRPClient(endpoint, project, **my_kwargs)
    raise ValueError(f"Unknown ReportPortal Client type requested: {client_type}")


__all__ = [
    "ClientType",
    "create_client",
    "current",
    "set_current",
    "RP",
    "RPClient",
    "AsyncRPClient",
    "BatchedRPClient",
    "ThreadedRPClient",
    "OutputType",
    "RPLogger",
    "RPLogHandler",
    "step",
]
