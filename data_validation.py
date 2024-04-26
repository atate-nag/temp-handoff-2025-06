from debug import dprint

class UnvalidatedData:
    def __init__(self, **kwargs):
        self.data = kwargs

    def __getitem__(self, key):
        return self.data.get(key)

    def __setitem__(self, key, value):
        self.data[key] = value

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set_data_for_state(self, state, **kwargs):
        self.data[state] = kwargs

    def get_data_for_state(self, state):
        return self.data.get(state, {})

class ValidatedData:
    def __init__(self, parent):
        self._data = {}
        self.parent = parent  # Reference to the Agent object

    def __getattr__(self, item):
        if item in self._data:
            return self._data[item]
        else:
            raise AttributeError(f"'ValidatedData' object has no attribute '{item}'")

    def set_data(self, key, value):
        if key in self.parent.permissions.get(self.parent.state, []):
            dprint(f"Permissions allow the update of {key} in state {self.parent.state}")
            self._data[key] = value
            dprint(f"setting self._data[{key}] to {value} now = {self._data[key]}")
        else:
            raise PermissionError(f"Setting {key} is not allowed in the {self.parent.state} state.")

