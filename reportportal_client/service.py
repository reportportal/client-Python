import os

import requests

from reportportal_client.model.response import (EntryCreatedRS,
                                                OperationCompletionRS)


def print_request(r):
    print("\n{0}: {1}\nRequest Body: {2}\nResponse Content: {3}\n".
          format(r.request.method, r.request.url, r.request.body, r.content))


class ReportPortalService(object):
    def __init__(self, endpoint, project, token, api_base=None):
        super(ReportPortalService, self).__init__()
        self.endpoint = endpoint
        if api_base is None:
            self.api_base = "api/v1"
        self.project = project
        self.token = token
        self.base_url = os.path.join(self.endpoint,
                                     self.api_base,
                                     self.project)
        self.headers = {"Content-Type": "application/json",
                        "Authorization": "{0} {1}".format("bearer",
                                                          self.token)}

    def start_launch(self, start_launch_rq):
        url = os.path.join(self.base_url, "launch")
        r = requests.post(url=url, headers=self.headers,
                          data=start_launch_rq.data)
        # print_request(r)
        return EntryCreatedRS(raw=r.text)

    def finish_launch(self, launch_id, finish_execution_rq):
        url = os.path.join(self.base_url, "launch", launch_id, "finish")
        r = requests.put(url=url, headers=self.headers,
                         data=finish_execution_rq.data)
        # print_request(r)
        return OperationCompletionRS(raw=r.text)

    def start_test_item(self, parent_item_id, start_test_item_rq):
        if parent_item_id is not None:
            url = os.path.join(self.base_url, "item", parent_item_id)
        else:
            url = os.path.join(self.base_url, "item")
        r = requests.post(url=url, headers=self.headers,
                          data=start_test_item_rq.data)
        # print_request(r)
        return EntryCreatedRS(raw=r.text)

    def finish_test_item(self, item_id, finish_test_item_rq):
        url = os.path.join(self.base_url, "item", item_id)
        r = requests.put(url=url, headers=self.headers,
                         data=finish_test_item_rq.data)
        # print_request(r)
        return OperationCompletionRS(raw=r.text)

    def log(self, save_log_rq):
        url = os.path.join(self.base_url, "log")
        r = requests.post(url=url, headers=self.headers,
                          data=save_log_rq.data)
        # print_request(r)
        return EntryCreatedRS(raw=r.text)
