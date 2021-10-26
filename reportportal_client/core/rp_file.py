"""This module contains classes representing RP file object."""


class RPFile(object):
    """Class representation for a file that will be attached to the log."""

    def __init__(self,
                 name=None,
                 content=None,
                 content_type=None,
                 data=None,
                 mime=None):
        """Initialize instance attributes.

        :param name:         File name
        :param content:      File content
        :param content_type: File content type (i.e. application/pdf)
        :param data:         File content
        :param mime:         File content type (i.e. application/pdf)
        """
        self.content = content or data
        self.content_type = content_type or mime
        self.name = name

    @property
    def payload(self):
        """Get HTTP payload for the request."""
        return {
            'content': self.content,
            'contentType': self.content_type,
            'name': self.name
        }
