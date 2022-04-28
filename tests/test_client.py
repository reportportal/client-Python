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

import pytest
from requests import Response
from requests.exceptions import ReadTimeout

from reportportal_client.helpers import timestamp
from reportportal_client.static.defines import NOT_FOUND


def connection_error(*args, **kwargs):
    raise ReadTimeout()


def response_error(*args, **kwargs):
    result = Response()
    result._content = '502 Gateway Timeout'.encode('ASCII')
    result.status_code = 502
    return result


@pytest.mark.parametrize(
    'requests_method, client_method, client_params, expected_result',
    [
        ('put', 'finish_launch', [timestamp()], NOT_FOUND),
        ('put', 'finish_test_item', ['test_item_id', timestamp()], NOT_FOUND),
        ('get', 'get_item_id_by_uuid', ['test_item_uuid'], NOT_FOUND),
        ('get', 'get_launch_info', [], {}),
        ('get', 'get_launch_ui_id', [], None),
        ('get', 'get_launch_ui_url', [], None),
        ('get', 'get_project_settings', [], {}),
        ('post', 'start_launch', ['Test Launch', timestamp()], NOT_FOUND),
        ('post', 'start_test_item', ['Test Item', timestamp(), 'STEP'],
         NOT_FOUND),
        ('put', 'update_test_item', ['test_item_id'], NOT_FOUND)
    ]
)
def test_connection_errors(rp_client, requests_method, client_method,
                           client_params, expected_result):
    rp_client.launch_id = 'test_launch_id'
    getattr(rp_client.session, requests_method).side_effect = connection_error
    result = getattr(rp_client, client_method)(*client_params)
    assert result is None

    getattr(rp_client.session, requests_method).side_effect = response_error
    result = getattr(rp_client, client_method)(*client_params)
    assert result == expected_result