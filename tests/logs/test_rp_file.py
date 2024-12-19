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

# noinspection PyPackageRequirements
import pytest

from reportportal_client.core.rp_file import RPFile


@pytest.mark.parametrize(["name"], [[""], [None], ["   "]])
def test_rp_file_name_should_not_be_empty(name):
    file = RPFile(name, b'{"test": true}', "application/json")

    payload = file.payload
    assert payload["name"]
    assert len(payload["name"]) > 10
