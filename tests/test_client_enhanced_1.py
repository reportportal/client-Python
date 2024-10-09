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
import warnings
from unittest import mock
import pytest

from reportportal_client.aio.client import ReconnectReason
from reportportal_client.aio.client import RetryingTask as Task
from reportportal_client.aio.client import TaskInfo
from reportportal_client.aio.client import DEFAULT_TASK_TIMEOUT
from reportportal_client.aio.client import DEFAULT_SHUTDOWN_TASK_TIMEOUT
from reportportal_client.aio.multiplexer import Multiplexer
from reportportal_client.aio.tasks import StateChangeTask, KeepAliveTask, PeriodicTask
from reportportal_client.client import RP, ProjectSettings
from reportportal_client.core.rp_issues import Issue
from reportportal_client.core.rp_requests import RPFile
from tests import REPORT_ENDPOINT_V1, ROOT_URI, PROJECT_NAME, LAUNCH_ID, NO_OP


def test_mp_init():
    rp = mock.RP()
    with Multiplexer() as mp:
        assert len(mp.rps) == 0
        assert mp._active is rp
        mp.add_child=RpChild(rp)

    assert mp._active is None


def test_get_next_child():
    rp = mock.RP()
    child = RpChild(rp)
    with Multiplexer() as mp:
        mp.add_child(child)
        assert mp.get_next_child() is child
        assert mp._active is child
        mp.add_child(rp)
        assert mp._active is rp


def test_get_next_child_with_shutdown():
    rp = mock.RP()
    rp.shutdown = mock.AsyncMock()
    child = RpChild(rp)
    with Multiplexer() as mp:
        mp.add_child(child)
        assert mp.get_next_child() is child
        mp.shutdown()
        assert rp.shutdown.called


class RpChild(Multiplexer):

    shutdown = NO_OP
    add_child = NO_OP
    remove_child = NO_OP


def test_shut_down_task():
    task_info = TaskInfo(0, 0.0001, 0.0001, 0)
    task = StateChangeTask(mock.AsyncMock(), task_info)
    loop = mock.Mock()
    loop.sock_connected = True
    loop.sock_coro = mock.AsyncMock()
    with warnings.catch_warnings():
        warnings.simplefilter(action='ignore', category=DeprecationWarning)
        result = yield from task.execute(loop)
    assert result
    assert task.state_name == 'CONNECTED'
    assert task.timeout_left <= 0
    assert task_info.connect_attempt == 0
    assert not loop.sock_coro.cancel.called

    task_info.connect_attempt = -1
    task = StateChangeTask(mock.AsyncMock(), task_info)
    with warnings.catch_warnings():
        warnings.simplefilter(action='ignore', category=DeprecationWarning)
        result = yield from task.execute(loop)
    assert result
    assert task.state_name == 'SHUTDOWN'
    assert task.timeout_left <= 0
    assert task_info.connect_attempt == -1
    assert loop.sock_coro.cancel.called


def test_reconnect_reason():
    reason = ReconnectReason(exception=ConnectionResetError)
    assert reason.value == 1
    reason = ReconnectReason(exception=EOFError)
    assert reason.value == 2
    reason = ReconnectReason(exception=RuntimeError)
    assert reason.value == 0


def test_reconnect_reason_shutdown():
    reason = ReconnectReason(shutdown=True)
    assert reason.value == -1


def test_task_execute():
    mock_loop = mock.AsyncMock()
    task = Task(NO_OP)
    assert task.execute(mock_loop) is None


def test_periodic_task():
    task = PeriodicTask(0.0001, NO_OP)
    assert round(task.period - 0.0001, 6) == 0
    assert task.coroutine is NO_OP


def test_keep_alive_task_init():
    rp = mock.RP()
    type(rp).keepalive_interval = mock.PropertyMock(return_value=0.0001)
    task = KeepAliveTask(rp)
    assert round(task.period - 0.0001, 6) == 0
    assert task.coroutine is rp.keepalive


def test_keep_alive_task_no_keep_alive():
    rp = mock.RP()
    type(rp).keepalive_interval = mock.PropertyMock(return_value=-1)
    task = KeepAliveTask(rp)
    assert task.period is DEFAULT_SHUTDOWN_TASK_TIMEOUT
    assert task.coroutine is NO_OP


def test_retry_task_init():
    task = Task(0.0001, NO_OP)
    assert round(task.retry_interval - 0.0001, 6) == 0
    assert task.coroutine is NO_OP


def test_retry_task():
    mock_loop = mock.AsyncMock()
    mock_loop.sock_coro = NO_OP
    task = Task(0.0001, NO_OP)
    result = yield from task.execute(mock_loop)
    assert result


def test_task_info():
    ti = TaskInfo(0, 1, 2, 3)
    assert ti.attempt is 0
    assert ti.connect_attempt is 1
    assert ti.timeout is 2
    assert ti.task_id is 3


def test_retrying_task():
    mock_loop = mock.AsyncMock()
    mock_coroutine = mock.AsyncMock()
    mock_coroutine.side_effect = [RuntimeError, RuntimeError, 'result']
    task = Task(0.1, mock_coroutine)
    result = yield from Task(1, task).execute(mock_loop)
    assert result == 'result'
    assert mock_coroutine.call_count == 3
    assert mock_loop.reconnect.call_count == 2


def test_retrying_task_immediate_result():
    mock_loop = mock.AsyncMock()
    mock_coroutine = mock.AsyncMock()
    mock_coroutine.side_effect = ['result']
    task = Task(0.1, mock_coroutine)
    result = yield from Task(1, task).execute(mock_loop)
    assert result == 'result'
    assert mock_coroutine.call_count == 1
    assert not mock_loop.reconnect.called


def test_retrying_task_exception():
    mock_loop = mock.AsyncMock()
    mock_coroutine = mock.AsyncMock()
    mock_coroutine.side_effect = [RuntimeError()]
    task = Task(0.1, mock_coroutine)
    with pytest.raises(RuntimeError):
        yield from Task(0.1, task).execute(mock_loop)


def test_retrying_task_shutdown():
    mock_loop = mock.AsyncMock()
    mock_coroutine = mock.AsyncMock()
    mock_coroutine.side_effect = [RuntimeError, RuntimeWarning]
    task = Task(0.1, mock_coroutine)
    with pytest.raises(RuntimeWarning):
        yield from Task(-1, task).execute(mock_loop)


def test_reconnect():
    mp = mock.Multiplexer()
    rp = mock.RP()
    type(rp).connected = mock.PropertyMock(side_effect=[True, False, False])
    rp.shutdown = mock.AsyncMock()
    rp.get_launch_id = mock.Mock(return_value=LAUNCH_ID)
    type(rp.settings).reconnect_attempts = mock.PropertyMock(return_value=3)
    rp.start = Task(0.1, mock.AsyncMock())
    rp.finish = Task(0.1, mock.AsyncMock())
    rp.notify_issue = mock.AsyncMock()
    rp.notify_test_finish = mock.AsyncMock()
    rp.log_batch = mock.AsyncMock()

    type(rp.settings).endpoint = mock.PropertyMock(REPORT_ENDPOINT_V1)
    type(rp.settings).project = mock.PropertyMock(PROJECT_NAME)
    rp.log_batch_size = 1
    rp.skip_analytics = True

    type(RP).root_uri = mock.PropertyMock(ROOT_URI)
    rp.project_settings = ProjectSettings(rp.settings)

    rp.log = mock.ASYNC_MOCK()
    rp.start_test_item = mock.ASYNC_MOCK()
    rp.finish_test_item = mock.ASYNC_MOCK()
    rp.update_test_item = mock.ASYNC_MOCK()
    rp.log_batch = mock.ASYNC_MOCK()
    rp.keepalive = mock.ASYNC_MOCK()
    rp.shutdown_tasks = [NO_OP, NO_OP]

    rp.item_stack.put(5)
    rp.item_stack.put(6)
    rp.item_stack.put(7)

    mp.add_child(rp)

    rp.launch_uuid_print = True
    rp.print_output = 'STDOUT'

    result = mp.shutdown()
    assert rp.shutdown.called
    assert result

    rp.shutdown_tasks = [NO_OP, ReconnectingTask()]

    rp.launch_uuid_print = True
    rp.print_output = 'STDERR'

    rp.item_stack.put(8)
    rp.item_stack.put(9)
    rp.item_stack.put(10)

    rp.launch_uuid_print = True
    rp.print_output = 'STDOUT'

    result = mp.shutdown()
    assert rp.shutdown.called
    assert not result


def test_reconnect_not_print():
    rp = mock.RP()
    type(rp).connected = mock.PropertyMock(side_effect=[True, False, False])
    rp.shutdown = mock.AsyncMock()
    rp.start = Task(0.1, mock.AsyncMock())
    rp.finish = Task(0.1, mock.AsyncMock())
    rp.notify_issue = mock.AsyncMock()
    rp.notify_test_finish = mock.AsyncMock()
    rp.log_batch = mock.AsyncMock()
    rp.launch_uuid_print = False
    rp.print_output = 'STDOUT'
    rp.log = mock.ASYNC_MOCK()
    rp.start_test_item = mock.ASYNC_MOCK()
    rp.finish_test_item = mock.ASYNC_MOCK()
    rp.update_test_item = mock.ASYNC_MOCK()
    rp.launch_id = LAUNCH_ID
    type(RP).root_uri = mock.PropertyMock(ROOT_URI)
    rp.project_settings = ProjectSettings(rp.settings)

    rp.item_stack.put(5)
    rp.item_stack.put(6)
    rp.item_stack.put(7)
    rp.launch_uuid_print = True

    result = rp.shutdown()
    assert rp.shutdown.called
    assert result


def test_rp_init():
    mp = mock.Multiplexer()
    rp = RP(endpoint='endpoint', project='project',
            api_key='api_key', client=mp)
    assert rp.endpoint == 'endpoint'
    assert rp.project == 'project'
    assert rp.api_key == 'api_key'
    assert rp.client is mp


def test_rp_start_launch():
    mp = mock.Multiplexer()
    rp = RP(endpoint='endpoint', project='project',
            api_key='api_key', client=mp)
    rp._create_launch = Task(0.1, mock.AsyncMock())
    result = rp.start_launch(None, None)
    assert result


def test_rp_start_test_item():
    mp = mock.Multiplexer()
    rp = RP(endpoint='endpoint', project='project',
            api_key='api_key', client=mp)
    rp._create_item = Task(0.1, mock.AsyncMock())
    result = rp.start_test_item(None, None, None)
    assert result


def test_rp_finish_test_item():
    mp = mock.Multiplexer()
    rp = RP(endpoint='endpoint', project='project',
            api_key='api_key', client=mp)
    rp._finish_item = Task(0.1, mock.AsyncMock())
    result = rp.finish_test_item(None, None)
    assert result


def test_rp_finish_launch():
    mp = mock.Multiplexer()
    rp = RP(endpoint='endpoint', project='project',
            api_key='api_key', client=mp)
    rp._finish_launch = Task(0.1, mock.AsyncMock())
    result = rp.finish_launch(None)
    assert result


def test_rp_update_test_item():
    mp = mock.Multiplexer()
    rp = RP(endpoint='endpoint', project='project',
            api_key='api_key', client=mp)
    rp._update_item = Task(0.1, mock.AsyncMock())
    result = rp.update_test_item(None)
    assert result


def test_rp_log():
    rp = mock.RP()
    rp._log = Task(0.1, mock.AsyncMock())
    rp.log_level = 1
    rp.log_batch_size = 2
    rp.log_batch_payload_size = 3
    result = rp.log(None, None, 'TEST')
    assert result


def test_rp_set_attributes():
    rp = RP()
    rp.toxic_set_attributes = mock.Mock()
    rp.set_attributes([])
    assert rp.toxic_set_attributes.called


def test_rp_set_ignore_attributes():
    rp = RP()
    rp.toxic_set_attributes = mock.Mock()
    rp.set_ignore_attributes([])
    assert rp.toxic_set_attributes.called


def test_rp_verify_retention():
    rp = RP()
    rp.toxic_verify_retention = mock.Mock()
    rp.verify_retention()
    assert rp.toxic_verify_retention.called


def test_rp_get_launch_info():
    rp = RP()
    rp._get_launch_info = Task(0.1, mock.AsyncMock())
    result = rp.get_launch_info(None)
    assert result


def test_rp_get_item_id_by_uuid():
    rp = RP()
    rp._get_item_id_by_uuid = Task(0.1, mock.AsyncMock())
    result = rp.get_item_id_by_uuid(None)
    assert result


def test_rp_get_launch_ui_id():
    rp = RP()
    rp._get_launch_ui_id = Task(0.1, mock.AsyncMock())
    result = rp.get_launch_ui_id()
    assert result


def test_rp_get_launch_ui_url():
    rp = RP()
    rp._get_launch_ui_url = Task(0.1, mock.AsyncMock())
    result = rp.get_launch_ui_url()
    assert result


def test_rp_get_project_settings():
    rp = RP()
    rp._get_project_settings = Task(0.1, mock.AsyncMock())
    result = rp.get_project_settings()
    assert result


def test_rp_clone():
    rp = RP()
    clone = rp.clone()
    assert type(clone) is RP


def test_rp_get_project_settings():
    rp = RP()
    rp._get_project_settings = Task(0.1, mock.AsyncMock())
    result = rp.get_project_settings()
    assert result


def test_rp_close():
    rp = RP()
    rp.shutdown = Task(0.1, mock.AsyncMock())
    rp.shutdown()


@mock.patch('threading.Timer', spec_set=True)
def test_periodic_timer(timer):
    task = PeriodicTask(0, mock.AsyncMock())
    rp = RP()
    rp.keepalive_interval = 0
    rp.keepalive_task = task
    rp.shutdown()
    assert timer.is_alive()


@mock.patch('threading.Timer', spec_set=True)
def test_not_periodic_timer(timer):
    task = PeriodicTask(-1, mock.AsyncMock())
    rp = RP()
    rp.keepalive_interval = 0
    rp.keepalive_task = task
    rp.shutdown()
    assert not timer.is_alive()


def test_rp_repr():
    rp = RP()
    assert repr(rp)


def test_issue_init():
    issue = Issue(comment='test')
    assert issue.comment == 'test'


def test_issue_to_payload():
    issue = Issue(comment='test', issue_type='issue')
    assert issue.to_payload() == {'comment': 'test', 'issue_type': 'issue',
                                 'autoAnalyzed': True, 'ignoreAnalyzer': True}


def test_issue_to_payload_external():
    external_issue = Issue(external_issue=Issue(issue_type='issue'))
    issue = external_issue.to_payload()['externalSystemIssues'][0]
    assert issue['url'] is None


def test_issue_to_payload_without_comment_and_issue():
    issue = Issue()
    assert issue.to_payload() == {
        'issue_type': 'issue',
        'autoAnalyzed': True,
        'ignoreAnalyzer': True,
        'comment': None
    }


def test_rpfile_init():
    rpfile = RPFile(name='name', content=b'content')
    assert rpfile.name == 'name'
    assert rpfile.content == b'content'


def test_rpfile_init_content_type():
    rpfile = RPFile(name='name', content=b'content', content_type='ct')
    assert rpfile.name == 'name'
    assert rpfile.content_type == 'ct'


def test_rpfile_payload():
    rpfile = RPFile(name='name', content=b'content')
    assert rpfile.payload == {'file': ('name', b'content', 'application/octet-stream')}
