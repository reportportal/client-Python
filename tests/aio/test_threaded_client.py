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

from reportportal_client.aio import ThreadedRPClient


def test_threaded_rp_client_pickling():
    client = ThreadedRPClient('http://localhost:8080', 'default_personal', api_key='test_key')
    pickled_client = pickle.dumps(client)
    unpickled_client = pickle.loads(pickled_client)
    assert unpickled_client is not None


async def __empty_string():
    return ""


def test_clone():
    args = ['http://endpoint', 'project']
    kwargs = {'api_key': 'api_key1', 'launch_uuid': 'launch_uuid', 'log_batch_size': 30,
              'log_batch_payload_limit': 30 * 1024 * 1024, 'task_timeout': 63, 'shutdown_timeout': 123}
    async_client = ThreadedRPClient(*args, **kwargs)
    task1 = async_client.create_task(__empty_string())
    task2 = async_client.create_task(__empty_string())
    task1.blocking_result()
    task2.blocking_result()
    async_client._add_current_item(task1)
    async_client._add_current_item(task2)
    client = async_client.client
    step_reporter = async_client.step_reporter
    cloned = async_client.clone()
    assert (
            cloned is not None
            and async_client is not cloned
            and cloned.client is not None
            and cloned.client is client
            and cloned.step_reporter is not None
            and cloned.step_reporter is not step_reporter
            and cloned._task_list is async_client._task_list
            and cloned._task_mutex is async_client._task_mutex
            and cloned._loop is async_client._loop
    )
    assert (
            cloned.endpoint == args[0]
            and cloned.project == args[1]
            and cloned.client.endpoint == args[0]
            and cloned.client.project == args[1]
    )
    assert (
            cloned.client.api_key == kwargs['api_key']
            and cloned.launch_uuid.blocking_result() == kwargs['launch_uuid']
            and cloned.log_batch_size == kwargs['log_batch_size']
            and cloned.log_batch_payload_limit == kwargs['log_batch_payload_limit']
            and cloned.task_timeout == kwargs['task_timeout']
            and cloned.shutdown_timeout == kwargs['shutdown_timeout']
    )
    assert cloned._item_stack.qsize() == 1 \
           and async_client.current_item() == cloned.current_item()
