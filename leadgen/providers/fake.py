import json

import trafilatura

from leadgen.config import FIXTURES_DIR
from leadgen.models import EmailHit


class FakeSearchProvider:
    def search(self, query: str, max_results: int) -> list[str]:
        data = json.loads((FIXTURES_DIR / "search.json").read_text(encoding="utf-8"))
        return data["urls"][:max_results]


class FakePageFetcher:
    def fetch(self, domain: str) -> dict[str, str]:
        pages = {}
        for html_file in sorted((FIXTURES_DIR / "sites" / domain).glob("*.html")):
            path = "" if html_file.stem == "index" else html_file.stem
            text = trafilatura.extract(html_file.read_text(encoding="utf-8"))
            if text:
                pages[f"https://{domain}/{path}"] = text
        return pages


class FakeEmailFinder:
    external = False

    def find(self, domain: str) -> list[EmailHit]:
        data = json.loads((FIXTURES_DIR / "emails.json").read_text(encoding="utf-8"))
        return [EmailHit.model_validate(item) for item in data.get(domain, [])]
