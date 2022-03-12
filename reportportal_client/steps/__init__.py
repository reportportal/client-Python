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
from threading import local
from reportportal_client.helpers import get_function_params

__INSTANCES = local()


class StepContext:
    def __init__(self, name, params):
        self.name = name
        self.params = params

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


def step(name_source, params=None):
    if params is None:
        params = set()
    if callable(name_source):
        name = name_source.__name__
        return StepContext(name, params)(name_source)
    else:
        return StepContext(name_source, params)
