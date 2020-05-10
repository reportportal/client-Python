from requests import Response
from typing import Any, Text, Optional

class RPClient:
    _launch_uuid: Optional[Text] = ...
    _token: Optional[Text] = ...
    api_version: Text = ...
    base_url: Text = ...
    password: Text = ...
    port: Optional[Text] = ...
    project_name: Text = ...
    username: Text = ...
    def __init__(
            self,
            base_url: Text,
            username: Text,
            password: Text,
            project_name: Text,
            api_version: Text,
            **kwargs: Any) -> None: ...
    @property
    def launch_uuid(self) -> Text: ...
    @property
    def token(self) -> Text: ...
    def _request(self,
                 uri: Text,
                 token: Text,
                 **kwargs: Any) -> Response: ...
    def start_launch(
            self,
            name: Text,
            start_time: Text,
            **kwargs: Any) -> None: ...
    def start_item(
            self,
            name: Text,
            start_time: Text,
            item_type: Text,
            launch_uuid: Text,
            parent_uuid: Optional[Text],
            **kwargs: Any) -> None: ...
    def finish_item(
            self,
            launch_uuid: Text,
            item_uuid: Text,
            end_time: Text,
            **kwargs: Any) -> None: ...
    def finish_launch(
            self,
            launch_uuid: Text,
            end_time: Text,
            **kwargs: Any) -> None: ...
    def save_log(
            self,
            launch_uuid: Text,
            log_time: Text,
            **kwargs: Any) -> None: ...
