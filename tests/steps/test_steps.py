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
from reportportal_client import step

NESTED_STEP_NAME = 'test nested step'
PARENT_STEP_ID = '123-123-1234-123'
NESTED_STEP_ID = '321-321-4321-321'


def test_nested_steps_are_skipped_without_parent(rp_client):
    with step(NESTED_STEP_NAME, rp_client=rp_client):
        print("Hello nested steps")
    assert rp_client.session.post.call_count == 0
    assert rp_client.session.put.call_count == 0


def test_nested_steps_reported_with_parent(rp_client):
    rp_client.step_reporter.set_parent('STEP', PARENT_STEP_ID)

    with step(NESTED_STEP_NAME, rp_client=rp_client):
        print("Hello nested steps")
    assert rp_client.session.post.call_count == 1
    assert rp_client.session.put.call_count == 1


def test_nested_step_name(rp_client):
    rp_client.step_reporter.set_parent('STEP', PARENT_STEP_ID)

    with step(NESTED_STEP_NAME, rp_client=rp_client):
        print("Hello nested steps")

    assert rp_client.session.post.call_args[1]['json']['name'] == \
           NESTED_STEP_NAME


def test_nested_step_times(rp_client):
    rp_client.step_reporter.set_parent('STEP', PARENT_STEP_ID)

    with step(NESTED_STEP_NAME, rp_client=rp_client):
        print("Hello nested steps")

    assert rp_client.session.post.call_args[1]['json']['startTime']
    assert rp_client.session.put.call_args[1]['json']['endTime']
