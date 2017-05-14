class Error(Exception):
    """General exception for package."""


class EntryCreatedError(Error):
    """Represents error in case no entry is created.

    No 'id' in the json response.
    """


class OperationCompletionError(Error):
    """Represents error in case of operation failure.

    No 'msg' in the json response.
    """
