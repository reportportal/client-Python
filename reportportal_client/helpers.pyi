from logging import Logger
from typing import Dict, List, Text

logger: Logger


def generate_uuid() -> str: ...


def convert_string(value: str) -> str: ...


def dict_to_payload(value: Dict) -> List[Dict]: ...


def gen_attributes(rp_attributes: List) -> List[Dict]: ...

def get_launch_sys_attrs() -> Dict[Text]: ...

def get_package_version(package_name: Text) -> Text: ...
