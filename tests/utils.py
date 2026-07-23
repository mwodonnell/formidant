class FakeMultidict:
    def __init__(self, pairs: list[tuple[str, str]]):
        self._data: dict[str, list[str]] = {}
        for key, value in pairs:
            self._data.setdefault(key, []).append(value)

    def keys(self) -> list[str]:
        return list(self._data.keys())

    def getlist(self, key: str) -> list[str]:
        return self._data[key]


class FakeUpload:
    def __init__(self, name: str, content: bytes, content_type: str | None = None):
        self.name = name
        self.size = len(content)
        self.content_type = content_type
        self._content = content

    def read(self) -> bytes:
        return self._content


class FakeFormData(FakeMultidict):
    def __init__(
        self, pairs: list[tuple[str, str]], files: dict[str, FakeUpload] | None = None
    ):
        super().__init__(pairs)
        self.files = files or {}
