class ErrorRS():
    pass


class ReportPortalException(Exception):
    def __init__(self, status_code, status_message, error_content, **kwargs):
        super(ReportPortalException, self).__init__(**kwargs)
        self.status_code = status_code
        self.status_message = status_message
        self.error_content = error_content

    @property
    def message(self):
        return "Report Portal returned error\n" \
               "Status code: {0}\n" \
               "Status message: {1}\n" \
               "Error Message: {2}\n" \
               "Error Type: {3}\n" \
               "Stack Trace: ".format(self.status_code,
                                      self.status_message,
                                      self.error_content["message"],
                                      self.error_content["type"])


class ReportPortalClientException(ReportPortalException):
    serialVersionUID = -3747137063782963453L

    def __init__(self, *args, **kwargs):
        super(ReportPortalClientException, self).__init__(*args, **kwargs)


class ReportPortalServerException(ReportPortalException):
    serialVersionUID = -3767279627075261149L

    def __init__(self, *args, **kwargs):
        super(ReportPortalServerException, self).__init__(*args, **kwargs)
