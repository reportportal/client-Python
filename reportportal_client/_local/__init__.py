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
"""Report Portal client context storing and retrieving module."""
from threading import local


__INSTANCES = local()


def current():
    """Return current Report Portal client."""
    if hasattr(__INSTANCES, 'current'):
        return __INSTANCES.current


def set_current(client):
    """Save Report Portal client as current.

    The method is not intended to use used by users. Report Portal client calls
    it itself when new client is created.

    :param client: Report Portal client
    """
    __INSTANCES.current = client
