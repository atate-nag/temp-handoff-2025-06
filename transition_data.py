class TransitionData:
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