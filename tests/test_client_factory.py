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

# noinspection PyPackageRequirements
import pytest

from reportportal_client import (create_client, ClientType, RPClient, AsyncRPClient, ThreadedRPClient,
                                 BatchedRPClient)


@pytest.mark.parametrize(
    'requested_type, expected_type',
    [
        (ClientType.SYNC, RPClient),
        (ClientType.ASYNC, AsyncRPClient),
        (ClientType.ASYNC_THREAD, ThreadedRPClient),
        (ClientType.ASYNC_BATCHED, BatchedRPClient),
    ]
)
def test_client_factory_types(requested_type: ClientType, expected_type):
    result = create_client(requested_type, 'http://endpoint', 'default_personal')
    assert isinstance(result, expected_type)
