#  Copyright (c) 2023 EPAM Systems
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

import json
import sys
import pytest

from unittest import mock

from reportportal_client.core.rp_responses import RPResponse, AsyncRPResponse


def json_error():
    raise json.JSONDecodeError('Expecting value: line 1 column 1 (char 0)', '<html />', 0)


@mock.patch('reportportal_client.core.rp_responses.logging.Logger.error')
def test_json_decode_error(error_log):
    response = mock.Mock()
    response.ok = False
    del response.status
    response.status_code = 404
    response.json.side_effect = json_error

    rp_response = RPResponse(response)
    assert rp_response.json is None
    error_log.assert_called_once()
    assert error_log.call_args_list[0][0][0] == ('Unable to decode JSON response, got failed response with code "404" '
                                                 'please check your endpoint configuration or API key')


@pytest.mark.skipif(sys.version_info < (3, 8),
                    reason='the test requires AsyncMock which was introduced in Python 3.8')
@mock.patch('reportportal_client.core.rp_responses.logging.Logger.error')
@pytest.mark.asyncio
async def test_json_decode_error_async(error_log):
    response = mock.AsyncMock()
    response.ok = False
    response.status = 403
    response.json.side_effect = json_error

    rp_response = AsyncRPResponse(response)
    assert await rp_response.json is None
    error_log.assert_called_once()
    assert error_log.call_args_list[0][0][0] == ('Unable to decode JSON response, got failed response with code "403" '
                                                 'please check your endpoint configuration or API key')
