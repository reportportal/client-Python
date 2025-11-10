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
import threading
from unittest import mock

# noinspection PyProtectedMember
from reportportal_client._internal.http import ClientSession
from reportportal_client._internal.services.auth import ApiKeyAuthSync


class OkHttpHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write("{}\n\n".encode("utf-8"))
        self.wfile.flush()


class UnauthorizedHttpHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        auth_header = self.headers.get("Authorization")
        if auth_header == "Bearer test_api_key":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write("{}\n\n".encode("utf-8"))
        else:
            self.send_response(401, "Unauthorized")
            self.end_headers()
            self.wfile.write("Unauthorized\n\n".encode("utf-8"))
        self.wfile.flush()


SERVER_PORT = 10000
SERVER_ADDRESS = ("", SERVER_PORT)
SERVER_CLASS = socketserver.TCPServer


# Allow socket reuse to avoid "Address already in use" errors
class ReuseAddrTCPServer(socketserver.TCPServer):
    allow_reuse_address = True


def get_http_server(
    *,
    server_handler,
    server_address=SERVER_ADDRESS,
):
    httpd = ReuseAddrTCPServer(server_address, server_handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd


def test_no_auth_request():
    """Test that requests work without authentication."""
    port = 10000
    session = ClientSession()

    with get_http_server(server_handler=OkHttpHandler, server_address=("", port)):
        with session:
            result = session.get(f"http://localhost:{port}/")
            assert result.ok
            assert result.status_code == 200


def test_auth_header_added_to_request():
    """Test that auth header is added to requests when auth is configured."""
    port = 10001
    auth = ApiKeyAuthSync("test_api_key")
    session = ClientSession(auth=auth)

    with get_http_server(server_handler=UnauthorizedHttpHandler, server_address=("", port)):
        with session:
            result = session.get(f"http://localhost:{port}/")
            assert result.ok
            assert result.status_code == 200


def test_auth_refresh_on_401():
    """Test that 401 response triggers auth refresh."""
    port = 10002

    # Create a mock auth that fails first, then succeeds
    auth = mock.Mock()
    auth.get = mock.Mock(side_effect=["Bearer invalid_token", "Bearer test_api_key"])
    auth.refresh = mock.Mock(return_value="Bearer test_api_key")

    session = ClientSession(auth=auth)

    with get_http_server(server_handler=UnauthorizedHttpHandler, server_address=("", port)):
        with session:
            result = session.get(f"http://localhost:{port}/")
            # First call to get() returns invalid token, which causes 401
            # Then refresh() is called and returns valid token
            # Request is retried with valid token and succeeds
            assert result.ok
            assert result.status_code == 200
            assert auth.get.call_count == 1
            assert auth.refresh.call_count == 1


def test_auth_refresh_only_once():
    """Test that auth refresh is only performed once per request."""
    port = 10003

    # Create a mock auth that always fails
    auth = mock.Mock()
    auth.get = mock.Mock(return_value="Bearer invalid_token")
    auth.refresh = mock.Mock(return_value="Bearer still_invalid_token")

    session = ClientSession(auth=auth)

    with get_http_server(server_handler=UnauthorizedHttpHandler, server_address=("", port)):
        with session:
            result = session.get(f"http://localhost:{port}/")
            # Auth refresh should only be attempted once
            assert not result.ok
            assert result.status_code == 401
            assert auth.get.call_count == 1
            assert auth.refresh.call_count == 1


def test_post_request_with_auth():
    """Test that POST requests work with authentication."""
    port = 10004
    auth = ApiKeyAuthSync("test_api_key")
    session = ClientSession(auth=auth)

    class PostHandler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            # Read the request body to avoid connection reset
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length:
                self.rfile.read(content_length)

            auth_header = self.headers.get("Authorization")
            if auth_header == "Bearer test_api_key":
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write("{}\n\n".encode("utf-8"))
            else:
                self.send_response(401, "Unauthorized")
                self.end_headers()
                self.wfile.write("Unauthorized\n\n".encode("utf-8"))
            self.wfile.flush()

    with get_http_server(server_handler=PostHandler, server_address=("", port)):
        with session:
            result = session.post(f"http://localhost:{port}/", data={"test": "data"})
            assert result.ok
            assert result.status_code == 200


def test_put_request_with_auth():
    """Test that PUT requests work with authentication."""
    port = 10005
    auth = ApiKeyAuthSync("test_api_key")
    session = ClientSession(auth=auth)

    class PutHandler(http.server.BaseHTTPRequestHandler):
        def do_PUT(self):
            # Read the request body to avoid connection reset
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length:
                self.rfile.read(content_length)

            auth_header = self.headers.get("Authorization")
            if auth_header == "Bearer test_api_key":
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write("{}\n\n".encode("utf-8"))
            else:
                self.send_response(401, "Unauthorized")
                self.end_headers()
                self.wfile.write("Unauthorized\n\n".encode("utf-8"))
            self.wfile.flush()

    with get_http_server(server_handler=PutHandler, server_address=("", port)):
        with session:
            result = session.put(f"http://localhost:{port}/", data={"test": "data"})
            assert result.ok
            assert result.status_code == 200


def test_403_triggers_auth_refresh():
    """Test that 403 response also triggers auth refresh."""
    port = 10006

    class ForbiddenHttpHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            auth_header = self.headers.get("Authorization")
            if auth_header == "Bearer test_api_key":
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write("{}\n\n".encode("utf-8"))
            else:
                self.send_response(403, "Forbidden")
                self.end_headers()
                self.wfile.write("Forbidden\n\n".encode("utf-8"))
            self.wfile.flush()

    # Create a mock auth that fails first, then succeeds
    auth = mock.Mock()
    auth.get = mock.Mock(side_effect=["Bearer invalid_token", "Bearer test_api_key"])
    auth.refresh = mock.Mock(return_value="Bearer test_api_key")

    session = ClientSession(auth=auth)

    with get_http_server(server_handler=ForbiddenHttpHandler, server_address=("", port)):
        with session:
            result = session.get(f"http://localhost:{port}/")
            assert result.ok
            assert result.status_code == 200
            assert auth.get.call_count == 1
            assert auth.refresh.call_count == 1


def test_mount_adapter():
    """Test that mount method allows mounting adapters."""
    import requests.adapters

    session = ClientSession()
    adapter = requests.adapters.HTTPAdapter(max_retries=3)

    # Test that mount method works without error
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    # Verify the adapter was mounted by checking internal session
    assert session._client.get_adapter("http://example.com") == adapter
    assert session._client.get_adapter("https://example.com") == adapter

    session.close()
