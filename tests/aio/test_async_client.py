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
import sys
from unittest import mock

# noinspection PyPackageRequirements
import pytest

from reportportal_client.aio import AsyncRPClient
from reportportal_client.helpers import timestamp


def test_async_rp_client_pickling():
    client = AsyncRPClient('http://localhost:8080', 'default_personal', api_key='test_key')
    pickled_client = pickle.dumps(client)
    unpickled_client = pickle.loads(pickled_client)
    assert unpickled_client is not None


def test_clone():
    args = ['http://endpoint', 'project']
    kwargs = {'api_key': 'api_key1', 'launch_uuid': 'launch_uuid', 'log_batch_size': 30,
              'log_batch_payload_limit': 30 * 1024 * 1024}
    async_client = AsyncRPClient(*args, **kwargs)
    async_client._add_current_item('test-321')
    async_client._add_current_item('test-322')
    client = async_client.client
    step_reporter = async_client.step_reporter
    cloned = async_client.clone()
    assert (
            cloned is not None
            and async_client is not cloned
            and cloned.client is not None
            and cloned.client is not client
            and cloned.step_reporter is not None
            and cloned.step_reporter is not step_reporter
    )
    assert (
            cloned.endpoint == args[0]
            and cloned.project == args[1]
            and cloned.client.endpoint == args[0]
            and cloned.client.project == args[1]
    )
    assert (
            cloned.client.api_key == kwargs['api_key']
            and cloned.launch_uuid == kwargs['launch_uuid']
            and cloned.log_batch_size == kwargs['log_batch_size']
            and cloned.log_batch_payload_limit == kwargs['log_batch_payload_limit']
    )
    assert cloned._item_stack.qsize() == 1 \
           and async_client.current_item() == cloned.current_item()


@pytest.mark.skipif(sys.version_info < (3, 8),
                    reason='the test requires AsyncMock which was introduced in Python 3.8')
@pytest.mark.asyncio
async def test_start_launch():
    aio_client = mock.AsyncMock()
    client = AsyncRPClient('http://endpoint', 'project', api_key='api_key',
                           client=aio_client)
    launch_name = 'Test Launch'
    start_time = str(1696921416000)
    description = 'Test Launch description'
    attributes = {'attribute_key': 'attribute_value'}
    rerun = True
    rerun_of = 'test_prent_launch_uuid'
    result = await client.start_launch(launch_name, start_time, description=description,
                                       attributes=attributes, rerun=rerun, rerun_of=rerun_of)

    assert result is not None
    assert client.launch_uuid == result
    aio_client.start_launch.assert_called_once()
    args, kwargs = aio_client.start_launch.call_args_list[0]
    assert args[0] == launch_name
    assert args[1] == start_time
    assert kwargs.get('description') == description
    assert kwargs.get('attributes') == attributes
    assert kwargs.get('rerun') == rerun
    assert kwargs.get('rerun_of') == rerun_of


@pytest.mark.skipif(sys.version_info < (3, 8),
                    reason='the test requires AsyncMock which was introduced in Python 3.8')
@pytest.mark.parametrize(
    'launch_uuid, method, params',
    [
        ('test_launch_uuid', 'start_test_item', ['Test Item', timestamp(), 'STEP']),
        ('test_launch_uuid', 'finish_test_item', ['test_item_id', timestamp()]),
        ('test_launch_uuid', 'get_launch_info', []),
        ('test_launch_uuid', 'get_launch_ui_id', []),
        ('test_launch_uuid', 'get_launch_ui_url', []),
        ('test_launch_uuid', 'log', [timestamp(), 'Test message']),
        (None, 'start_test_item', ['Test Item', timestamp(), 'STEP']),
        (None, 'finish_test_item', ['test_item_id', timestamp()]),
        (None, 'get_launch_info', []),
        (None, 'get_launch_ui_id', []),
        (None, 'get_launch_ui_url', []),
        (None, 'log', [timestamp(), 'Test message']),
    ]
)
@pytest.mark.asyncio
async def test_launch_uuid_usage(launch_uuid, method, params):
    started_launch_uuid = 'new_test_launch_uuid'
    aio_client = mock.AsyncMock()
    aio_client.start_launch.return_value = started_launch_uuid
    client = AsyncRPClient('http://endpoint', 'project', api_key='api_key',
                           client=aio_client, launch_uuid=launch_uuid, log_batch_size=1)
    actual_launch_uuid = await client.start_launch('Test Launch', timestamp())
    await getattr(client, method)(*params)
    finish_launch_message = await client.finish_launch(timestamp())

    if launch_uuid is None:
        aio_client.start_launch.assert_called_once()
        assert actual_launch_uuid == started_launch_uuid
        assert client.launch_uuid == started_launch_uuid
        aio_client.finish_launch.assert_called_once()
        assert finish_launch_message
    else:
        aio_client.start_launch.assert_not_called()
        assert actual_launch_uuid == launch_uuid
        assert client.launch_uuid == launch_uuid
        aio_client.finish_launch.assert_not_called()
        assert finish_launch_message == ''
    assert client.launch_uuid == actual_launch_uuid

    if method == 'log':
        assert len(getattr(aio_client, 'log_batch').call_args_list) == 2
        args, kwargs = getattr(aio_client, 'log_batch').call_args_list[0]
        batch = args[0]
        assert isinstance(batch, list)
        assert len(batch) == 1
        log = batch[0]
        assert log.launch_uuid == actual_launch_uuid
        assert log.time == params[0]
        assert log.message == params[1]
    else:
        getattr(aio_client, method).assert_called_once()
        args, kwargs = getattr(aio_client, method).call_args_list[0]
        assert args[0] == actual_launch_uuid
        for i, param in enumerate(params):
            assert args[i + 1] == param


@pytest.mark.skipif(sys.version_info < (3, 8),
                    reason='the test requires AsyncMock which was introduced in Python 3.8')
@pytest.mark.asyncio
async def test_start_item_tracking(async_client: AsyncRPClient):
    aio_client = async_client.client

    started_launch_uuid = 'new_test_launch_uuid'
    aio_client.start_launch.return_value = started_launch_uuid
    test_item_id = 'test_item_uuid'
    aio_client.start_test_item.return_value = test_item_id

    await async_client.start_launch('Test Launch', timestamp())
    actual_item_id = await async_client.start_test_item('Test Item Name', timestamp(), 'STEP')
    assert actual_item_id == test_item_id
    assert async_client.current_item() == test_item_id

    await async_client.finish_test_item(actual_item_id, timestamp())
    assert async_client.current_item() is None
