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

from typing import Optional, Dict, Any, Callable, Union

from reportportal_client.client import RP
from reportportal_client.aio import Task


class StepReporter:
    client: RP = ...

    def __init__(self, rp_client: RP) -> None: ...

    def start_nested_step(self,
                          name: str,
                          start_time: str,
                          parameters: Dict = ...,
                          **kwargs: Any) -> Union[Optional[str], Task[str]]: ...

    def finish_nested_step(self,
                           item_id: str,
                           end_time: str,
                           status: str,
                           **kwargs: Any) -> None: ...


class Step:
    name: str = ...
    params: Dict = ...
    status: str = ...
    client: Optional[RP] = ...
    __item_id: Union[Optional[str], Task[str]] = ...

    def __init__(self,
                 name: str,
                 params: Dict,
                 status: str,
                 rp_client: Optional[RP]) -> None: ...

    def __enter__(self) -> None: ...

    def __exit__(self, exc_type, exc_val, exc_tb) -> None: ...

    def __call__(self, func: Callable) -> Callable: ...


def step(name_source: Union[Callable, str],
         params: Dict = ...,
         status: str = ...,
         rp_client: RP = ...) -> None: ...
