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
#
#  https://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License
import http.server
import socketserver
import threading
import time
from unittest import mock

import aiohttp

# noinspection PyPackageRequirements
import pytest

# noinspection PyProtectedMember
from reportportal_client._internal.aio.http import RetryingClientSession

HTTP_TIMEOUT_TIME = 1.2


class OkHttpHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write("{}\n\n".encode("utf-8"))
        self.wfile.flush()


class TimeoutHttpHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        time.sleep(HTTP_TIMEOUT_TIME)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write("{}\n\n".encode("utf-8"))
        self.wfile.flush()


class ResetHttpHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.wfile.close()


class ErrorHttpHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(500, "Internal Server Error")
        self.end_headers()
        self.wfile.write("Internal Server Error\n\n".encode("utf-8"))
        self.wfile.flush()


class ThrottlingHttpHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(429, "Throttling")
        self.end_headers()
        self.wfile.write("Throttling\n\n".encode("utf-8"))
        self.wfile.flush()


SERVER_PORT = 8000
SERVER_ADDRESS = ("", SERVER_PORT)
SERVER_CLASS = socketserver.TCPServer
SERVER_HANDLER_CLASS = http.server.BaseHTTPRequestHandler


def get_http_server(server_class=SERVER_CLASS, server_address=SERVER_ADDRESS, server_handler=SERVER_HANDLER_CLASS):
    httpd = server_class(server_address, server_handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd


async def execute_http_request(port, retry_number, server_class, timeout_seconds, protocol="http"):
    timeout = aiohttp.ClientTimeout(connect=timeout_seconds, sock_read=timeout_seconds)
    connector = aiohttp.TCPConnector(force_close=True)
    session = RetryingClientSession(
        f"{protocol}://localhost:{port}",
        timeout=timeout,
        max_retry_number=retry_number,
        base_retry_delay=0.01,
        connector=connector,
    )
    # noinspection PyProtectedMember
    parent_request = session._client.get
    async_mock = mock.Mock()
    async_mock.side_effect = parent_request
    exception = None
    result = None
    with get_http_server(server_handler=server_class, server_address=("", port)):
        with mock.patch("reportportal_client._internal.aio.http.ClientSession.get", async_mock):
            async with session:
                start_time = time.time()
                try:
                    result = await session.get("/")
                except Exception as exc:
                    exception = exc
                total_time = time.time() - start_time
    return async_mock, exception, result, total_time


@pytest.mark.parametrize(
    "server_class, port, expected_delay, timeout_seconds, is_exception",
    [
        (TimeoutHttpHandler, 8001, 14.4, 1.0, True),
        (ResetHttpHandler, 8002, 8.4, 1.0, True),
        (ErrorHttpHandler, 8003, 1.1, 1.0, False),
        (ThrottlingHttpHandler, 8004, 27.93, 1.0, False),
    ],
)
@pytest.mark.asyncio
async def test_retry_on_request_error(server_class, port, expected_delay, timeout_seconds, is_exception):
    retry_number = 5
    async_mock, exception, result, total_time = await execute_http_request(
        port, retry_number, server_class, timeout_seconds
    )
    if is_exception:
        assert exception is not None
    else:
        assert exception is None
        assert not result.ok
    assert async_mock.call_count == 1 + retry_number
    assert total_time > expected_delay
    assert total_time < expected_delay * 1.5


@pytest.mark.asyncio
async def test_no_retry_on_ok_request():
    retry_number = 5
    port = 8000
    async_mock, exception, result, total_time = await execute_http_request(port, retry_number, OkHttpHandler, 1)
    assert exception is None
    assert result.ok
    assert async_mock.call_count == 1
    assert total_time < 1


@pytest.mark.asyncio
async def test_no_retry_on_not_retryable_error():
    retry_number = 5
    port = 8005
    async_mock, exception, result, total_time = await execute_http_request(
        port, retry_number, OkHttpHandler, 1, protocol="https"
    )
    assert exception is not None
    assert result is None
    assert async_mock.call_count == 1
    assert total_time < 1
