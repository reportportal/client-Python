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

"""This module contains common Pytest fixtures and hooks for unit tests."""

from unittest import mock

# noinspection PyPackageRequirements
from pytest import fixture

from reportportal_client.aio.client import Client, AsyncRPClient, BatchedRPClient, ThreadedRPClient
from reportportal_client.client import RPClient


@fixture
def response():
    """Cook up a mock for the Response with specific arguments."""

    def inner(ret_code, ret_value):
        """Set up response with the given parameters.

        :param ret_code:  Return code for the response
        :param ret_value: Return value for the response
        :return:          Mocked Response object with the given parameters
        """
        with mock.patch('requests.Response') as resp:
            resp.status_code = ret_code
            resp.json.return_value = ret_value
            return resp

    return inner


@fixture
def rp_client():
    """Prepare instance of the RPClient for testing."""
    client = RPClient('http://endpoint', 'project', 'api_key')
    client.session = mock.Mock()
    client._skip_analytics = True
    return client


@fixture
def aio_client():
    """Prepare instance of the Client for testing."""
    client = Client('http://endpoint', 'project', api_key='api_key')
    client._session = mock.AsyncMock()
    client._skip_analytics = True
    return client


@fixture
def async_client():
    """Prepare instance of the AsyncRPClient for testing."""
    client = AsyncRPClient('http://endpoint', 'project', api_key='api_key',
                           client=mock.AsyncMock())
    return client


@fixture
def batched_client():
    """Prepare instance of the AsyncRPClient for testing."""
    client = BatchedRPClient('http://endpoint', 'project', api_key='api_key',
                             client=mock.AsyncMock())
    return client


@fixture
def threaded_client():
    """Prepare instance of the AsyncRPClient for testing."""
    client = ThreadedRPClient('http://endpoint', 'project', api_key='api_key',
                              client=mock.AsyncMock())
    return client
