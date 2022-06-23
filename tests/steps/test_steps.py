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
import random
import time

from reportportal_client import step
from reportportal_client._local import set_current
from six.moves import mock

NESTED_STEP_NAME = 'test nested step'
PARENT_STEP_ID = '123-123-1234-123'
NESTED_STEP_ID = '321-321-4321-321'


def test_nested_steps_are_skipped_without_parent(rp_client):
    with step(NESTED_STEP_NAME):
        pass

    assert rp_client.session.post.call_count == 0
    assert rp_client.session.put.call_count == 0


def test_nested_steps_reported_with_parent(rp_client):
    rp_client._item_stack.append(PARENT_STEP_ID)

    with step(NESTED_STEP_NAME):
        pass

    assert rp_client.session.post.call_count == 1
    assert rp_client.session.put.call_count == 1


def test_nested_steps_are_skipped_without_client(rp_client):
    rp_client._item_stack.append(PARENT_STEP_ID)
    set_current(None)
    with step(NESTED_STEP_NAME):
        pass

    assert rp_client.session.post.call_count == 0
    assert rp_client.session.put.call_count == 0


def test_nested_step_name(rp_client):
    rp_client._item_stack.append(PARENT_STEP_ID)

    with step(NESTED_STEP_NAME):
        pass

    assert rp_client.session.post.call_args[1]['json']['name'] == \
           NESTED_STEP_NAME


def test_nested_step_times(rp_client):
    rp_client._item_stack.append(PARENT_STEP_ID)

    with step(NESTED_STEP_NAME):
        pass

    assert rp_client.session.post.call_args[1]['json']['startTime']
    assert rp_client.session.put.call_args[1]['json']['endTime']


@step
def nested_step():
    pass


def test_nested_step_decorator(rp_client):
    rp_client._item_stack.append(PARENT_STEP_ID)
    nested_step()

    assert rp_client.session.post.call_count == 1
    assert rp_client.session.put.call_count == 1
    assert len(rp_client._log_manager._batch) == 0


def test_nested_step_failed(rp_client):
    rp_client._item_stack.append(PARENT_STEP_ID)
    try:
        with step(NESTED_STEP_NAME):
            raise AssertionError
    except AssertionError:
        pass
    assert rp_client.session.post.call_count == 1
    assert rp_client.session.put.call_count == 1
    assert rp_client.session.put.call_args[1]['json']['status'] == 'FAILED'


def test_nested_step_custom_status(rp_client):
    rp_client._item_stack.append(PARENT_STEP_ID)
    with step(NESTED_STEP_NAME, status='INFO'):
        pass
    assert rp_client.session.post.call_count == 1
    assert rp_client.session.put.call_count == 1
    assert rp_client.session.put.call_args[1]['json']['status'] == 'INFO'


def test_nested_step_custom_status_failed(rp_client):
    rp_client._item_stack.append(PARENT_STEP_ID)
    try:
        with step(NESTED_STEP_NAME, status='INFO'):
            raise AssertionError
    except AssertionError:
        pass
    assert rp_client.session.post.call_count == 1
    assert rp_client.session.put.call_count == 1
    assert rp_client.session.put.call_args[1]['json']['status'] == 'FAILED'


def item_id_gen(*args, **kwargs):
    item_id = 'post-{}-{}'.format(
        str(round(time.time() * 1000)),
        random.randint(0, 9999))
    result = mock.Mock()
    result.text = '{{"id": "{}"}}'.format(item_id)
    result.json = lambda: {'id': item_id}
    return result


@step
def nested_step_params(param1, param2, param3=None):
    pass


def test_verify_parameters_logging_default_value(rp_client):
    rp_client.session.post.side_effect = item_id_gen
    rp_client._item_stack.append(PARENT_STEP_ID)
    nested_step_params(1, 'two')
    assert len(rp_client._log_manager._batch) == 1
    assert rp_client._log_manager._batch[0].message \
           == "Parameters: param1: 1; param2: two"


def test_verify_parameters_logging_no_default_value(rp_client):
    rp_client.session.post.side_effect = item_id_gen
    rp_client._item_stack.append(PARENT_STEP_ID)
    nested_step_params(1, 'two', 'three')
    assert len(rp_client._log_manager._batch) == 1
    assert rp_client._log_manager._batch[0].message \
           == "Parameters: param1: 1; param2: two; param3: three"


def test_verify_parameters_logging_named_value(rp_client):
    rp_client.session.post.side_effect = item_id_gen
    rp_client._item_stack.append(PARENT_STEP_ID)
    nested_step_params(1, 'two', param3='three')
    assert len(rp_client._log_manager._batch) == 1
    assert rp_client._log_manager._batch[0].message \
           == "Parameters: param1: 1; param2: two; param3: three"


def test_verify_parameters_inline_logging(rp_client):
    rp_client.session.post.side_effect = item_id_gen
    rp_client._item_stack.append(PARENT_STEP_ID)
    with step(NESTED_STEP_NAME, params={'param1': 1, 'param2': 'two'}):
        pass
    assert len(rp_client._log_manager._batch) == 1
    assert rp_client._log_manager._batch[0].message \
           == "Parameters: param1: 1; param2: two"


@step
def parent_nested_step():
    nested_step()


def test_two_level_nested_step_decorator(rp_client):
    rp_client._item_stack.append(PARENT_STEP_ID)
    rp_client.session.post.side_effect = item_id_gen
    parent_nested_step()

    assert rp_client.session.post.call_count == 2
    assert rp_client.session.put.call_count == 2
    assert len(rp_client._log_manager._batch) == 0

    request_uri = rp_client.session.post.call_args_list[0][0][0]
    first_parent_id = request_uri[request_uri.rindex('/') + 1:]
    request_uri = rp_client.session.post.call_args_list[1][0][0]
    second_parent_id = request_uri[request_uri.rindex('/') + 1:]

    request_uri = rp_client.session.put.call_args_list[0][0][0]
    first_id = request_uri[request_uri.rindex('/') + 1:]
    request_uri = rp_client.session.put.call_args_list[1][0][0]
    second_id = request_uri[request_uri.rindex('/') + 1:]

    assert first_parent_id == PARENT_STEP_ID
    assert second_parent_id.startswith('post-')
    assert first_id.startswith('post-')
    assert second_id.startswith('post-')
    assert first_id != second_id


def test_verify_manual_client_bypass_step(rp_client):
    set_current(None)
    rp_client._item_stack.append(PARENT_STEP_ID)
    with step(NESTED_STEP_NAME, rp_client=rp_client):
        pass
    assert rp_client.session.post.call_count == 1
    assert rp_client.session.put.call_count == 1
