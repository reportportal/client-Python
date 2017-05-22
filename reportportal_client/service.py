import json
import requests
from logging import getLogger

logger = getLogger(__name__)


def _get_id(response):
    try:
        return json.loads(response)["id"]
    except KeyError:
        raise Exception("raw: {0}".format(response))


def _get_msg(response):
    try:
        return json.loads(response)["msg"]
    except KeyError:
        raise Exception("raw: {0}".format(response))


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


class ReportPortalService(object):
    """Service class with report portal event callbacks."""

    def __init__(self, endpoint, project, token, api_base="api/v1"):
        """Init the service class.

        Args:
            endpoint: endpoint of report portal service.
            project: project name to use for launch names.
            token: authorization token.
            api_base: defaults to api/v1, can be changed to other version.
        """
        super(ReportPortalService, self).__init__()
        self.endpoint = endpoint
        self.api_base = api_base
        self.project = project
        self.token = token
        self.base_url = uri_join(self.endpoint,
                                 self.api_base,
                                 self.project)

        self.session = requests.Session()
        self.session.headers["Authorization"] = "bearer {0}".format(self.token)
        self.stack = []
        self.launch_id = None

    def terminate(self):
        pass

    def start_launch(self, name=None, description=None, tags=None, start_time=None,
                     mode=None):
        data = {
            "name": name,
            "description": description,
            "tags": tags,
            "start_time": start_time,
            "mode": mode
        }
        url = uri_join(self.base_url, "launch")
        r = self.session.post(url=url, json=data)
        self.launch_id = _get_id(r.text)
        self.stack.append(None)
        logger.debug("start_launch - Stack: {0}". format(self.stack))
        return self.launch_id

    def finish_launch(self, end_time=None, status=None):
        data = {
            "end_time": end_time,
            "status": status
        }
        url = uri_join(self.base_url, "launch", self.launch_id, "finish")
        r = self.session.put(url=url, json=data)
        return _get_msg(r.text)

    def start_test_item(self, name=None, description=None, tags=None,
                        start_time=None, type=None):
        data = {
            "name": name,
            "description": description,
            "tags": tags,
            "start_time": start_time,
            "launch_id": self.launch_id,
            "type": type,
        }
        parent_item_id = self.stack[-1]
        if parent_item_id is not None:
            url = uri_join(self.base_url, "item", parent_item_id)
        else:
            url = uri_join(self.base_url, "item")
        r = self.session.post(url=url, json=data)

        _id = _get_id(r.text)
        self.stack.append(_id)
        return _id

    def finish_test_item(self, end_time=None, status=None, issue=None):
        data = {
            "end_time": end_time,
            "status": status,
            "issue": issue,
        }
        item_id = self.stack.pop()
        url = uri_join(self.base_url, "item", item_id)
        r = self.session.put(url=url, json=data)
        return _get_msg(r.text)

    def log(self, time=None, message=None, level=None, attachment=None):
        data = {
            "item_id": self.stack[-1],
            "time": time,
            "message": message,
            "level": level,
            "attachment": attachment
        }
        if attachment:
            return self.log_batch([data])
        else:
            url = uri_join(self.base_url, "log")
            r = self.session.post(url=url, json=data)
            return _get_id(r.text)

    def log_batch(self, log_data):
        """Logs batch of messages with attachment.

        Args:
            log_data: list of log records.
            log record is a dict of;
                time, message, level, attachment
                attachment is a dict of:
                    name: name of attachment
                    data: fileobj or content
                    mime: content type for attachment

        Returns:
            
        """

        url = uri_join(self.base_url, "log")

        attachments = []
        for log_item in log_data:
            log_item["item_id"] = self.stack[-1]
            attachment = log_item.get("attachment", None)
            del log_item["attachment"]

            if attachment:
                log_item["file"] = {"name": attachment["name"]}
                attachments.append(("file", (
                    attachment["name"],
                    attachment["data"],
                    attachment["mime"]
                )))

        files = [
            ("json_request_part", (None, json.dumps(log_data), "application/json")),
        ]
        files.extend(attachments)
        r = self.session.post(url=url, files=files)
        logger.debug("log_batch respose: {}".format(r.text))

        return r.text
