import json
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
            api_base: defaults to api/v1, can be changed to other version.
        """
        super(ReportPortalService, self).__init__()
        self.endpoint = endpoint
        if api_base is None:
            self.api_base = "api/v1"
        self.project = project
        self.token = token
        self.base_url = self.uri_join(self.endpoint,
                                      self.api_base,
                                      self.project)

        self.session = requests.Session()
        self.session.headers["Authorization"] = "bearer {0}".format(self.token)

    @staticmethod
    def uri_join(*uri_parts):
        """Join uri parts.

        Avoiding usage of urlparse.urljoin and os.path.join
        as it does not clearly join parts.

        Args:
            *uri_parts: tuple of values for join, can contain back and forward
                        slashes (will be stripped up).

        Returns:
            An uri string.
        """
        return '/'.join(str(s).strip('/').strip('\\') for s in uri_parts)

    def start_launch(self, start_launch_rq):
        url = self.uri_join(self.base_url, "launch")
        r = self.session.post(url=url, json=start_launch_rq.as_dict())
        return EntryCreatedRS(raw=r.text)

    def finish_launch(self, launch_id, finish_execution_rq):
        url = self.uri_join(self.base_url, "launch", launch_id, "finish")
        r = self.session.put(url=url, json=finish_execution_rq.as_dict())
        return OperationCompletionRS(raw=r.text)

    def start_test_item(self, parent_item_id, start_test_item_rq):
        if parent_item_id is not None:
            url = self.uri_join(self.base_url, "item", parent_item_id)
        else:
            url = self.uri_join(self.base_url, "item")
        r = self.session.post(url=url, json=start_test_item_rq.as_dict())
        return EntryCreatedRS(raw=r.text)

    def finish_test_item(self, item_id, finish_test_item_rq):
        url = self.uri_join(self.base_url, "item", item_id)
        r = self.session.put(url=url, json=finish_test_item_rq.as_dict())
        return OperationCompletionRS(raw=r.text)

    def log(self, save_log_rq):
        url = self.uri_join(self.base_url, "log")
        r = self.session.post(url=url, json=save_log_rq.as_dict())
        return EntryCreatedRS(raw=r.text)

    def attach(self, save_log_rq, name, data, mime="application/octet-stream"):
        """Logs message with attachment.

        Args:
            save_log_rq: SaveLogRQ instance
            name: name of attachment
            data: fileobj or content
            mime: content type for attachment

        Returns:
            An instance of EntryCreatedRS.
        """
        url = self.uri_join(self.base_url, "log")
        dct = save_log_rq.as_dict()
        dct["file"] = {"name": name}
        files = {
            "json_request_part": (None, json.dumps([dct]), "application/json"),
            "file": (name, data, mime)
        }
        r = self.session.post(url=url, files=files)
        return EntryCreatedRS(raw=r.text)
