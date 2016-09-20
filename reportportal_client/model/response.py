import json


class RS(object):
    def __init__(self, raw):
        super(RS, self).__init__()
        self.raw = raw


class EntryCreatedRS(RS):
    def __init__(self, raw):
        super(EntryCreatedRS, self).__init__(raw)

    @property
    def id(self):
        try:
            return json.loads(self.raw)["id"]
        except KeyError as error:
            error.message += "Raw: {0}".format(self.raw)
            raise

    def as_dict(self):
        return {"id": self.id}


class OperationCompletionRS(RS):
    def __init__(self, raw):
        super(OperationCompletionRS, self).__init__(raw)

    @property
    def msg(self):
        try:
            return json.loads(self.raw)["msg"]
        except KeyError as error:
            error.message += "Raw: {0}".format(self.raw)
            raise

    def as_dict(self):
        return {"msg": self.msg}
