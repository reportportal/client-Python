import os

import requests

from .model import (EntryCreatedRS, OperationCompletionRS)


class ReportPortalService(object):
    """Service class with report portal event callbacks."""

    def __init__(self, endpoint, project, token, api_base=None):
        """Init the service class.

        Args:
            endpoint: endpoint of report portal service.
            project: project name to use for launch names.
            token: authorization token.
            api_base: defaults to api/v1, can be customized to use another version.
        """
        super(ReportPortalService, self).__init__()
        self.endpoint = endpoint
        if api_base is None:
            self.api_base = "api/v1"
        self.project = project
        self.token = token
        self.base_url = self.uri_join_safe(self.endpoint,
                                           self.api_base,
                                           self.project)
        self.headers = {"Content-Type": "application/json",
                        "Authorization": "{0} {1}".format("bearer",
                                                          self.token)}
        self.session = requests.Session()

    @staticmethod
    def uri_join_safe(*uri_parts):
        """Safe join of uri parts for our case.

        Avoiding usage of urlparse.urljoin and os.path.join as it does not clearly join parts.

        Args:
            *uri_parts: tuple of values for join, can contain back and forward slashes (will be stripped up).

        Returns:
            Safely joined uri parts.
        """
        stripped = [str(i).strip('/').strip('\\') for i in uri_parts]
        return '/'.join(stripped)

    def start_launch(self, start_launch_rq):
        url = self.uri_join_safe(self.base_url, "launch")
        r = self.session.post(url=url, headers=self.headers,
                              data=start_launch_rq.data)
        return EntryCreatedRS(raw=r.text)

    def finish_launch(self, launch_id, finish_execution_rq):
        url = self.uri_join_safe(self.base_url, "launch", launch_id, "finish")
        r = self.session.put(url=url, headers=self.headers,
                             data=finish_execution_rq.data)
        return OperationCompletionRS(raw=r.text)

    def start_test_item(self, parent_item_id, start_test_item_rq):
        if parent_item_id is not None:
            url = self.uri_join_safe(self.base_url, "item", parent_item_id)
        else:
            url = self.uri_join_safe(self.base_url, "item")
        r = self.session.post(url=url, headers=self.headers,
                              data=start_test_item_rq.data)
        return EntryCreatedRS(raw=r.text)

    def finish_test_item(self, item_id, finish_test_item_rq):
        url = self.uri_join_safe(self.base_url, "item", item_id)
        r = self.session.put(url=url, headers=self.headers,
                             data=finish_test_item_rq.data)
        return OperationCompletionRS(raw=r.text)

    def log(self, save_log_rq):
        url = self.uri_join_safe(self.base_url, "log")
        r = self.session.post(url=url, headers=self.headers,
                              data=save_log_rq.data)
        return EntryCreatedRS(raw=r.text)
