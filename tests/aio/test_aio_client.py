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

import pickle
from unittest import mock

import aiohttp
import pytest

from reportportal_client.aio.client import Client
from reportportal_client.aio.http import RetryingClientSession, DEFAULT_RETRY_NUMBER
from reportportal_client.static.defines import NOT_SET


def test_client_pickling():
    client = Client('http://localhost:8080', 'default_personal', api_key='test_key')
    pickled_client = pickle.dumps(client)
    unpickled_client = pickle.loads(pickled_client)
    assert unpickled_client is not None


@pytest.mark.parametrize(
    'retry_num, expected_class, expected_param',
    [
        (1, RetryingClientSession, 1),
        (0, aiohttp.ClientSession, NOT_SET),
        (-1, aiohttp.ClientSession, NOT_SET),
        (None, aiohttp.ClientSession, NOT_SET),
        (NOT_SET, RetryingClientSession, DEFAULT_RETRY_NUMBER)
    ]
)
def test_retries_param(retry_num, expected_class, expected_param):
    client = Client('http://localhost:8080', 'default_personal', api_key='test_key',
                    retries=retry_num)
    session = client.session
    assert isinstance(session, expected_class)
    if expected_param is not NOT_SET:
        assert getattr(session, f'_RetryingClientSession__retry_number') == expected_param
