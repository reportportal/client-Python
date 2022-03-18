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
import logging
from functools import wraps

from reportportal_client._local import current
from reportportal_client.helpers import get_function_params, timestamp
from reportportal_client.static.defines import NOT_FOUND

NESTED_STEP_ITEMS = ('step', 'scenario', 'before_class', 'before_groups',
                     'before_method', 'before_suite', 'before_test',
                     'after_test', 'after_suite', 'after_class',
                     'after_groups', 'after_method')

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


# noinspection PyUnresolvedReferences
class StepReporter:
    def __init__(self, rp_client):
        self.__levels = []
        self.client = rp_client

    def set_parent(self, item_type, parent_id):
        if parent_id is not NOT_FOUND:
            if item_type.lower() in NESTED_STEP_ITEMS:
                self.__levels.append(parent_id)

    def get_parent(self):
        if len(self.__levels) > 0:
            return self.__levels[-1]

    def remove_parent(self, parent_id):
        if len(self.__levels) > 0 and self.__levels[-1] == parent_id:
            return self.__levels.pop()

    def start_nested_step(self,
                          name,
                          start_time,
                          parameters=None,
                          **kwargs):
        parent_id = self.get_parent()
        if parent_id is None:
            return
        return self.client.start_test_item(name, start_time, 'step',
                                           has_stats=False,
                                           parameters=parameters,
                                           parent_item_id=parent_id)

    def finish_nested_step(self,
                           item_id,
                           end_time,
                           status=None,
                           **kwargs):
        if not self.remove_parent(item_id):
            return
        return self.client.finish_test_item(item_id, end_time, status=status)


class Step:
    def __init__(self, name, params, status, rp_client):
        self.name = name
        self.params = params
        self.status = status
        self.client = rp_client
        self.__item_id = None

    def __enter__(self):
        # Cannot call _local.current() early since it will be initialized
        # before client put something in there
        rp_client = self.client if self.client else current()
        if not rp_client:
            return
        self.__item_id = rp_client.step_reporter \
            .start_nested_step(self.name, timestamp(), parameters=self.params)
        if self.params:
            param_list = [
                str(key) + ": " + str(value)
                for key, value in sorted(self.params.items())
            ]
            param_str = 'Parameters: ' + '; '.join(param_list)
            rp_client.log(timestamp(), param_str, level='INFO',
                          item_id=self.__item_id)

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Cannot call _local.current() early since it will be initialized
        # before client put something in there
        rp_client = self.client if self.client else current()
        if not rp_client:
            return
        # Avoid failure in case if 'rp_client' was 'None' on function start
        if not self.__item_id:
            return
        step_status = self.status
        if any((exc_type, exc_val, exc_tb)):
            step_status = 'FAILED'
        rp_client.step_reporter \
            .finish_nested_step(self.__item_id, timestamp(), step_status)

    def __call__(self, func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            __tracebackhide__ = True
            params = self.params
            if params is None:
                params = get_function_params(func, args, kwargs)
            with Step(self.name, params, self.status, self.client):
                return func(*args, **kwargs)

        return wrapper


def step(name_source, params=None, status='PASSED', rp_client=None):
    if callable(name_source):
        name = name_source.__name__
        return Step(name, params, status, rp_client)(name_source)
    return Step(str(name_source), params, status, rp_client)
