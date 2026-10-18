import re
from collections import Counter
from urllib.parse import unquote

import trafilatura

from leadgen.models import EmailHit
from leadgen.providers.http_fetcher import HttpPageFetcher

ROLE_LOCAL_PARTS = {"info", "sales", "hello", "contact", "office", "partners", "zakaz"}
EMAIL_RE = re.compile(r"[a-z0-9._%+-]+@[a-z0-9-]+(?:\.[a-z0-9-]+)*\.[a-z]{2,}", re.IGNORECASE)
# logo@2x.png в тексте страницы выглядит как адрес
NOT_EMAIL_ENDINGS = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp")


class SiteEmailFinder:
    """Адреса со страниц, которые уже загрузил фетчер: mailto-ссылки и адреса в тексте контактов."""

    external = False

    def __init__(self, fetcher: HttpPageFetcher):
        self.fetcher = fetcher

    def find(self, domain: str) -> list[EmailHit]:
        hits = {}
        # Страницы уже в кэше после fetch_pages: сетевых запросов здесь нет.
        for kind, (url, html) in self.fetcher.fetch_html(domain, Counter()).items():
            doc = trafilatura.load_html(html)
            if doc is None:
                continue
            addresses = [
                unquote(href[len("mailto:"):]).split("?")[0]
                for href in doc.xpath("//a/@href")
                if href.lower().startswith("mailto:")
            ]
            if kind == "contacts":
                addresses += EMAIL_RE.findall(doc.text_content())
            for address in addresses:
                address = address.strip().lower()
                if address in hits or not EMAIL_RE.fullmatch(address) or address.endswith(NOT_EMAIL_ENDINGS):
                    continue
                hits[address] = EmailHit(
                    address=address,
                    kind="role" if address.split("@")[0] in ROLE_LOCAL_PARTS else "personal",
                    source=url,
                    confidence="high",  # адрес опубликован на сайте самой компании
                )
        return list(hits.values())
