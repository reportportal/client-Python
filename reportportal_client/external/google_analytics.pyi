from logging import Logger
import requests
from .constants import GA_ENDPOINT as GA_ENDPOINT, GA_INSTANCE as GA_INSTANCE
from typing import Text

logger: Logger

def _get_client_info() -> tuple: ...

def _get_platform_info() -> str: ...

def send_event(agent_name: Text, agent_version: Text) -> requests.Response: ...
