class FakeMultidict:
    def __init__(self, pairs: list[tuple[str, str]]):
        self._data: dict[str, list[str]] = {}
        for key, value in pairs:
            self._data.setdefault(key, []).append(value)

    def keys(self) -> list[str]:
        return list(self._data.keys())

    def getlist(self, key: str) -> list[str]:
        return self._data[key]
