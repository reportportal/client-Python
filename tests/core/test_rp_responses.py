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
from unittest import mock

# noinspection PyPackageRequirements
import pytest

from reportportal_client.core.rp_responses import AsyncRPResponse, RPResponse


class JSONDecodeError(ValueError):
    pass


def json_error():
    raise json.JSONDecodeError("Expecting value: line 1 column 1 (char 0)", "<html />", 0)


def custom_error():
    raise JSONDecodeError("Expecting value: line 1 column 1 (char 0)")


@mock.patch("reportportal_client.core.rp_responses.logging.Logger.error")
@pytest.mark.parametrize(
    "ok, response_code, error_function, expected_message",
    [
        (
            False,
            404,
            json_error,
            'Unable to decode JSON response, got failed response with code "404" please check your '
            "endpoint configuration or API key",
        ),
        (
            True,
            200,
            json_error,
            'Unable to decode JSON response, got passed response with code "200" please check your '
            "endpoint configuration or API key",
        ),
        (
            True,
            200,
            custom_error,
            'Unable to decode JSON response, got passed response with code "200" please check your '
            "endpoint configuration or API key",
        ),
    ],
)
def test_custom_decode_error(error_log, ok, response_code, error_function, expected_message):
    response = mock.Mock()
    response.ok = ok
    del response.status
    response.status_code = response_code
    response.json.side_effect = error_function

    rp_response = RPResponse(response)
    assert rp_response.json is None
    error_log.assert_called_once()
    assert error_log.call_args_list[0][0][0] == expected_message


@mock.patch("reportportal_client.core.rp_responses.logging.Logger.error")
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "ok, response_code, error_function, expected_message",
    [
        (
            False,
            404,
            json_error,
            'Unable to decode JSON response, got failed response with code "404" please check your '
            "endpoint configuration or API key",
        ),
        (
            True,
            200,
            json_error,
            'Unable to decode JSON response, got passed response with code "200" please check your '
            "endpoint configuration or API key",
        ),
        (
            True,
            200,
            custom_error,
            'Unable to decode JSON response, got passed response with code "200" please check your '
            "endpoint configuration or API key",
        ),
    ],
)
async def test_json_decode_error_async(error_log, ok, response_code, error_function, expected_message):
    response = mock.AsyncMock()
    response.ok = ok
    response.status = response_code
    response.json.side_effect = error_function

    rp_response = AsyncRPResponse(response)
    assert await rp_response.json is None
    error_log.assert_called_once()
    assert error_log.call_args_list[0][0][0] == expected_message
