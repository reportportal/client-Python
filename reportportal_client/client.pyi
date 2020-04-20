from typing import Any
from requests import Response

class Client:
    _token: (str, None) = ...
    base_url: str = ...
    port: (str, None) = ...
    username: str = ...
    password: str = ...
    project_name: str = ...
    api_version: str = ...
    def __init__(
            self,
            base_url: str,
            username: str,
            password: str,
            project_name: str,
            api_version: str,
            **kwargs: Any) -> None: ...
    @property
    def token(self) -> str: ...
    def _request(self,
                 uri: str,
                 token: str,
                 **kwargs: Any) -> Response: ...
    def start_launch(
            self,
            name: str,
            start_time: str,
            **kwargs: Any) -> None: ...
    def start_item(
            self,
            name: str,
            start_time: str,
            item_type: str,
            launch_uuid: str,
            parent_uuid: str=...,
            **kwargs: Any) -> None: ...
    def finish_item(
            self,
            launch_uuid: str,
            item_uuid: str,
            end_time: str,
            **kwargs: Any) -> None: ...
    def finish_launch(
            self,
            launch_uuid: str,
            end_time: str) -> None: ...
    def save_log(
            self,
            launch_uuid: str,
            log_time: str,
            **kwargs: Any) -> None: ...
