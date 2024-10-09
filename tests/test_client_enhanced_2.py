#  Copyright (c) 2022 https://reportportal.io .
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
import pytest

from reportportal_client.aio.client import RetryingClient, DEFAULT_TASK_TIMEOUT


@pytest.mark.asyncio
async def test_aio_init_default_values():
    client = RetryingClient('https://endpoint')

    assert client.endpoint == 'https://endpoint'
    assert client.api_v1 == 'v1'
    assert client.api_v2 == 'v2'
    assert client.base_url_v1 == 'https://endpoint/api/v1'
    assert client.base_url_v2 == 'https://endpoint/api/v2'
    assert client.project is None
    assert client.api_key is None
    assert client.requests_session_lock is not None
    assert client.flat_channel is not None
    assert client.max_retry_number == 3
    assert client.task_timeout == DEFAULT_TASK_TIMEOUT


@pytest.mark.asyncio
async def test_aio_init_custom_values():
    client = RetryingClient(
        endpoint='https:mypage.mycompany.com',
        project='my_project',
        api_key='api_key',
        api_v1='v0',
        api_v2='v3',
        max_retry_number=5,
        task_timeout=5
    )

    assert client.endpoint == 'https:mypage.mycompany.com'
    assert client.api_v1 == 'v0'
    assert client.api_v2 == 'v3'
    assert client.base_url_v1 == 'https:mypage.mycompany.com/api/v0'
    assert client.base_url_v2 == 'https:mypage.mycompany.com/api/v3'
    assert client.project == 'my_project'
    assert client.api_key == 'api_key'
    assert client.requests_session_lock is not None
    assert client.flat_channel is not None
    assert client.max_retry_number == 5
    assert client.task_timeout == 5


@pytest.mark.asyncio
async def test_create_session():
    client = RetryingClient('https://endpoint', api_key='api_key')

    await client.create_session()
    assert client.session is not None
    assert client.lock is not None


@pytest.mark.asyncio
async def test__get_entry_point_v1():
    client = RetryingClient('https://endpoint', api_key='api_key')

    ep = await client._get_entry_point(v1=True)
    assert ep == 'https://endpoint/api/v1'


@pytest.mark.asyncio
async def test__get_entry_point_v2():
    client = RetryingClient('https://endpoint', api_key='api_key')

    ep = await client._get_entry_point(v1=False)
    assert ep == 'https://endpoint/api/v2'


@pytest.mark.asyncio
async def test__get_launch_url():
    client = RetryingClient('https://endpoint', api_key='api_key')
    client.project = 'my_project'

    url = await client._get_launch_url('my_launch')
    assert url == 'https://endpoint/api/v2/my_project/launches/async'


@pytest.mark.asyncio
async def test__get_item_url():
    client = RetryingClient('https://endpoint', api_key='api_key')
    client.project = 'my_project'
    pid = 'my_pid'

    url = await client._get_item_url(pid)
    assert url == f'https://endpoint/api/v2/my_project/item/{pid}'


@pytest.mark.asyncio
async def test__get_log_url():
    client = RetryingClient('https://endpoint', api_key='api_key')
    client.project = 'my_project'

    url = await client._get_log_url()
    assert url == 'https://endpoint/api/v1/my_project/log'
