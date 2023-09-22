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
import http.server
import socketserver
import sys
import threading
import time
from unittest import mock

import aiohttp
import pytest

from reportportal_client.aio.http import RetryingClientSession

HTTP_TIMEOUT_TIME = 1.2


class TimeoutHttpHandler(http.server.BaseHTTPRequestHandler):

    def do_GET(self):
        time.sleep(HTTP_TIMEOUT_TIME)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write('{}\n\n'.encode("utf-8"))
        self.wfile.flush()


SERVER_PORT = 8000
SERVER_ADDRESS = ('', SERVER_PORT)
SERVER_CLASS = socketserver.TCPServer
SERVER_HANDLER_CLASS = http.server.BaseHTTPRequestHandler


def get_http_server(server_class=SERVER_CLASS, server_address=SERVER_ADDRESS,
                    server_handler=SERVER_HANDLER_CLASS):
    httpd = server_class(server_address, server_handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd


@pytest.mark.skipif(sys.version_info < (3, 8),
                    reason="the test requires Python 3.8 or higher")
@pytest.mark.asyncio
async def test_retry_on_request_timeout():
    timeout = aiohttp.ClientTimeout(connect=1, sock_read=1)
    session = RetryingClientSession('http://localhost:8000', timeout=timeout, max_retry_number=5,
                                    base_retry_delay=0.01)
    parent_request = super(type(session), session)._request
    async_mock = mock.AsyncMock()
    async_mock.side_effect = parent_request
    exception = None
    with get_http_server(server_handler=TimeoutHttpHandler):
        with mock.patch('reportportal_client.aio.http.ClientSession._request', async_mock):
            async with session:
                start_time = time.time()
                try:
                    await session.get('/')
                except Exception as exc:
                    exception = exc
                total_time = time.time() - start_time
    retries_and_delays = 6 + 0.02 + 0.4 + 8
    assert exception is not None
    assert async_mock.call_count == 6
    assert total_time > retries_and_delays
    assert total_time < retries_and_delays * 1.5
