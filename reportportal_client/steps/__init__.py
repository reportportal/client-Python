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

"""ReportPortal Nested Step handling module.

The module for handling and reporting ReportPortal Nested Steps inside python
test frameworks. Import 'step' function to use it as decorator or together with
'with' keyword to divide your tests on smaller steps.

Usage as decorator:
.. highlight:: python
.. code-block:: python

    from reportportal_client import step

    @step
    def my_nested_step():
        pass

    def test_my_nested_step():
        my_nested_step()


Usage with 'with' keyword:
.. highlight:: python
.. code-block:: python

    from reportportal_client import step

    def test_my_nested_step():
        with step('My nested step', status='INFO'):
            pass

"""
from functools import wraps

# noinspection PyProtectedMember
from reportportal_client._internal.local import current
from reportportal_client.helpers import get_function_params, timestamp

NESTED_STEP_ITEMS = ('step', 'scenario', 'before_class', 'before_groups',
                     'before_method', 'before_suite', 'before_test',
                     'after_test', 'after_suite', 'after_class',
                     'after_groups', 'after_method')


# noinspection PyUnresolvedReferences
class StepReporter:
    """Nested Steps context handling class."""

    def __init__(self, rp_client):
        """Initialize required attributes.

        :param rp_client: ReportPortal client which will be used to report
                          steps
        """
        self.client = rp_client

    def start_nested_step(self,
                          name,
                          start_time,
                          parameters=None,
                          **kwargs):
        """Start Nested Step on ReportPortal.

        :param name:       Nested Step name
        :param start_time: Nested Step start time
        :param parameters: Nested Step parameters
        """
        parent_id = self.client.current_item()
        if not parent_id:
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
        """Finish a Nested Step on ReportPortal.

        :param item_id:  Nested Step item ID
        :param end_time: Nested Step finish time
        :param status:   Nested Step finish status
        """
        return self.client.finish_test_item(item_id, end_time, status=status)


class Step:
    """Step context handling class."""

    def __init__(self, name, params, status, rp_client):
        """Initialize required attributes.

        :param name:      Nested Step name
        :param params:    Nested Step parameters
        :param status:    Nested Step status which will be reported on
                          successful step finish
        :param rp_client: ReportPortal client which will be used to report
                          the step
        """
        self.name = name
        self.params = params
        self.status = status
        self.client = rp_client
        self.__item_id = None

    def __enter__(self):
        """Enter the runtime context related to this object."""
        # Cannot call _local.current() early since it will be initialized
        # before client put something in there
        rp_client = self.client or current()
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
        """Exit the runtime context related to this object."""
        # Cannot call local.current() early since it will be initialized before client put something in there
        rp_client = self.client or current()
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
        """Wrap and call a function reference.

        :param func: function reference
        """

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
    """Nested step report function.

    Create a Nested Step inside a test method on ReportPortal.
    :param name_source: a function or string which will be used as step's name
    :param params:      nested step parameters which will be reported as the
                        first step entry. If 'name_source' is a function
                        reference and this parameter is not specified, they
                        will be taken from the function.
    :param status:      the status which will be reported after the step
                        passed. Can be any of legal ReportPortal statuses.
                        E.G.: PASSED, WARN, INFO, etc. Default value is PASSED
    :param rp_client:   overrides ReportPortal client which will be used in
                        step reporting
    :return: a step context object
    """
    if callable(name_source):
        name = name_source.__name__
        return Step(name, params, status, rp_client)(name_source)
    return Step(str(name_source), params, status, rp_client)
