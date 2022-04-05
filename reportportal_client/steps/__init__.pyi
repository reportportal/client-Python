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

from typing import Text, Optional, Dict, Any, Callable, Union

from reportportal_client.client import RPClient


class StepReporter:
    client: RPClient = ...

    def __init__(self, rp_client: RPClient) -> None: ...

    def start_nested_step(self,
                          name: Text,
                          start_time: Text,
                          parameters: Dict = ...,
                          **kwargs: Any) -> Text: ...

    def finish_nested_step(self,
                           item_id: Text,
                           end_time: Text,
                           status: Text,
                           **kwargs: Any) -> None: ...


class Step:
    name: Text = ...
    params: Dict = ...
    status: Text = ...
    client: Optional[RPClient] = ...
    __item_id: Optional[Text] = ...

    def __init__(self,
                 name: Text,
                 params: Dict,
                 status: Text,
                 rp_client: Optional[RPClient]) -> None: ...

    def __enter__(self) -> None: ...

    def __exit__(self, exc_type, exc_val, exc_tb) -> None: ...

    def __call__(self, func: Callable) -> Callable: ...


def step(name_source: Union[Callable, Text],
         params: Dict = ...,
         status: Text = ...,
         rp_client: RPClient = ...) -> None: ...
