"""This module contains Report Portal Client class."""


class Client(object):
    """Report portal client."""

    def __init__(self, base_url, username, password, project_name, api_version,
                 **kwargs):
        """Initialize required attributes."""
        self.base_url = base_url
        self.port = kwargs.get('port', None)
        self.username = username
        self.password = password
        self.project_name = project_name
        self.api_version = api_version
        self._token = None

    @property
    def token(self):
        """Get the token."""
        return self._token

    def _request(self, uri, token, **kwargs):
        """Make Rest calls with necessary params.

        :param uri:   Request URI
        :param token: Access token
        :return:      :class:`Response <Response>` object
        """

    def start_launch(self, name, start_time, **kwargs):
        """Start launch.

        :param name:        Name of launch
        :param start_time:  Launch start time
        """
        # uri = f'/api/{self.api_version}/{self.project_name}/launch'

    def start_item(self, name, start_time, item_type, launch_uuid,
                   parent_uuid='', **kwargs):
        """Start case/step/nested step item.

        :param name:        Name of test item
        :param start_time:  Test item start time
        :param item_type:   Type of test item
        :param launch_uuid: Launch UUID
        :param parent_uuid: Parent test item UUID
        """
        # uri = f'/api/{self.api_version}/{self.project_name}/item/
        # {parent_uuid}'

    def finish_item(self, launch_uuid, item_uuid, end_time, **kwargs):
        """Finish suite/case/step/nested step item.

        :param launch_uuid: Launch UUID
        :param item_uuid:   Item UUID
        :param end_time:    Item end time
        """
        # uri = f'/api/{self.api_version}/{self.project_name}/item/{item_uuid}'

    def finish_launch(self, launch_uuid, end_time):
        """Finish launch.

        :param launch_uuid: Launch UUID
        :param end_time:    Launch end time
        """
        # uri = f'/api/{self.api_version}/{self.project_name}/launch' \
        #       f'/{launch_uuid}/finish'

    def save_log(self, launch_uuid, log_time, **kwargs):
        """Save logs for test items.

        :param launch_uuid: Launch UUID
        :param log_time:    Log time
        """
        # uri = f'/api/{self.api_version}/{self.project_name}/log'
