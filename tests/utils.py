from html.parser import HTMLParser


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


class FormHarvester(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.pairs: list[tuple[str, str]] = []
        self._select: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "input":
            name = attributes.get("name")
            input_type = attributes.get("type", "text")
            if not name or input_type == "file":
                return
            if input_type == "checkbox":
                if "checked" in attributes:
                    self.pairs.append((name, attributes.get("value") or "on"))
            else:
                self.pairs.append((name, attributes.get("value") or ""))
        elif tag == "select":
            self._select = attributes.get("name")
        elif tag == "option" and self._select and "selected" in attributes:
            self.pairs.append((self._select, attributes.get("value") or ""))

    def handle_endtag(self, tag: str) -> None:
        if tag == "select":
            self._select = None


def harvest_form_values(html: str) -> list[tuple[str, str]]:
    harvester = FormHarvester()
    harvester.feed(html)
    return harvester.pairs


class FakeFormData(FakeMultidict):
    def __init__(
        self, pairs: list[tuple[str, str]], files: dict[str, FakeUpload] | None = None
    ):
        super().__init__(pairs)
        self.files = files or {}
