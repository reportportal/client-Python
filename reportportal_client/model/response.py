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
        except KeyError:
            print("{0} object has no attribute 'id'".format(self.raw))
            return None

    def as_dict(self):
        try:
            return {"id": self.id}
        except KeyError:
            return json.loads(self.raw)


class OperationCompletionRS(RS):
    def __init__(self, raw):
        super(OperationCompletionRS, self).__init__(raw)

    @property
    def msg(self):
        try:
            return json.loads(self.raw)["msg"]
        except KeyError:
            print("{0} object has no attribute 'msg'".format(self.raw))
            return None

    def as_dict(self):
        try:
            return {"msg": json.loads(self.raw)["msg"]}
        except KeyError:
            return json.loads(self.raw)
