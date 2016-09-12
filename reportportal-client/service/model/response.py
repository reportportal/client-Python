import json


class EntryCreatedRS(object):
    def __init__(self, id=None, raw=None):
        super(EntryCreatedRS, self).__init__()
        self.id = id
        self.raw = raw
        if raw is not None:
            self.id = json.loads(raw)["id"]

    def as_dict(self):
        return {"id": self.id}


class OperationCompletionRS(object):
    def __init__(self, msg=None, raw=None):
        super(OperationCompletionRS, self).__init__()
        self.msg = msg
        if raw is not None:
            self.msg = json.loads(raw)["msg"]

    def as_dict(self):
        return {"msg": self.msg}
