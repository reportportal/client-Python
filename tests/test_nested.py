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


@step
def nested_step():
    print("Inside nested step")


@step
def nested_step_params(param1, param2, named_param=None):
    print("Inside nested step with params")


def test_function_level_nested_steps_start_stop():
    nested_step()
    nested_step_params(1, 2, named_param="test")

    with step("Code level nested step", {"test": "value"}):
        print("Inside code-level nested step")
