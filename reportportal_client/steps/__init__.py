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
from functools import wraps
from reportportal_client.helpers import get_function_params, evaluate_status


class StepContext:
    def __init__(self):
        self.parent_id = None
        self.statuses = {}

    def set_status(self, status):
        if self.parent_id is not None:
            if self.parent_id in self.statuses:
                self.statuses[self.parent_id] = \
                    evaluate_status(self.statuses[self.parent_id], status)
            else:
                self.statuses[self.parent_id] = status

    def get_status(self):
        if self.parent_id is not None:
            return None
        return self.statuses[self.parent_id]


class Step:
    def __init__(self, name, params, client):
        self.name = name
        self.params = params
        self.client = client

    def __enter__(self):
        # Step start here
        print("Nested step start with params: " + str(self.params))
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Step stop here
        print("Nested step stop")
        pass

    def __call__(self, func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            __tracebackhide__ = True
            self.params = get_function_params(func, args, kwargs)
            with self:
                return func(*args, **kwargs)
        return wrapper


def step(func_or_name, name=None, params=None, client=None):
    if params is None:
        params = set()
    if callable(func_or_name):
        if name is None:
            name = func_or_name.__name__
        return Step(name, params, client)(func_or_name)
    else:
        return Step(func_or_name, params, client)
