#  Copyright (c) 2022 EPAM Systems
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

from typing import Dict, List, Optional, Text


class Issue:
    _external_issues: List = ...
    auto_analyzed: bool = ...
    comment: Text = ...
    ignore_analyzer: bool = ...
    issue_type: Text = ...

    def __init__(self,
                 issue_type: Text,
                 comment: Optional[Text] = ...,
                 auto_analyzed: Optional[bool] = ...,
                 ignore_analyzer: Optional[bool] = ...) -> None: ...

    def external_issue_add(self, issue: ExternalIssue) -> None: ...

    @property
    def payload(self) -> Dict: ...


class ExternalIssue:
    bts_url: Text = ...
    bts_project: Text = ...
    submit_date: Text = ...
    ticket_id: Text = ...
    url: Text = ...

    def __init__(self,
                 bts_url: Optional[Text] = ...,
                 bts_project: Optional[Text] = ...,
                 submit_date: Optional[Text] = ...,
                 ticket_id: Optional[Text] = ...,
                 url: Optional[Text] = ...) -> None: ...

    @property
    def payload(self) -> Dict: ...
