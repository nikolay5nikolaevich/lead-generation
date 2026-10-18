import threading
import time
from collections import Counter
from urllib.parse import unquote, urljoin, urlsplit

import httpx
import trafilatura
from protego import Protego
from trafilatura.utils import decode_file

from leadgen.config import MAX_CHARS_PER_PAGE, MAX_PAGES_PER_SITE
from leadgen.storage.cache import PageCache

USER_AGENT = "leadgen-bot/0.1 (B2B lead research; respects robots.txt)"

# Какие страницы искать среди ссылок главной: слово должно быть в пути ссылки или в её тексте.
# Порядок важен: при нехватке MAX_PAGES_PER_SITE отбрасываются последние.
PAGE_KEYWORDS = {
    "about": ["about", "o-kompanii", "o-nas", "company", "о компании", "о нас"],
    "services": ["services", "uslugi", "услуги", "solutions", "решения"],
    "contacts": ["contact", "kontakt", "контакт"],
}


class HttpPageFetcher:
    def __init__(self, cache: PageCache):
        self.cache = cache
        self.client = httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=10, follow_redirects=True)
        # Итог по всем доменам: сколько запросов к сайтам ушло в сеть, сколько взято из кэша.
        self.stats = Counter()
        self._stats_lock = threading.Lock()  # fetch вызывается из параллельных веток

    def fetch(self, domain: str) -> dict[str, str]:
        started = time.monotonic()
        stats = Counter()
        texts = {}
        for url, html in self.fetch_html(domain, stats).values():
            text = trafilatura.extract(html)
            if text:
                texts[url] = text[:MAX_CHARS_PER_PAGE]
        print(f"  {domain}: страниц с текстом {len(texts)}; запросы к сайту: сеть {stats['network']}, кэш {stats['cache']}; {time.monotonic() - started:.1f} с")
        with self._stats_lock:
            self.stats.update(stats)
        return texts

    def fetch_html(self, domain: str, stats: Counter) -> dict[str, tuple[str, str]]:
        """Вернуть {вид страницы: (url, html)}. Виды: home и ключи PAGE_KEYWORDS."""
        # Protego, а не urllib.robotparser: тот читает частое «Disallow: /?» как «Disallow: /»
        # и не понимает «*».
        robots = Protego.parse(self._get(f"https://{domain}/robots.txt", stats))
        home_url = f"https://{domain}/"
        if not robots.can_fetch(home_url, USER_AGENT):
            print(f"  {domain}: robots.txt запрещает обход")
            return {}
        home = self._get(home_url, stats)
        if not home:
            return {}

        pages = {"home": (home_url, home)}
        for kind, url in self._find_links(domain, home_url, home).items():
            if len(pages) >= MAX_PAGES_PER_SITE:
                break
            if not robots.can_fetch(url, USER_AGENT):
                continue
            html = self._get(url, stats)
            if html:
                pages[kind] = (url, html)
        return pages

    def _find_links(self, domain: str, home_url: str, html: str) -> dict[str, str]:
        doc = trafilatura.load_html(html)
        if doc is None:
            return {}
        found = {}
        for link in doc.xpath("//a[@href]"):
            url = urljoin(home_url, link.get("href")).split("#")[0]
            parts = urlsplit(url)
            host = parts.hostname or ""
            if parts.scheme not in ("http", "https") or not (host == domain or host.endswith("." + domain)):
                continue
            if parts.path in ("", "/") or url in found.values():
                continue
            haystack = (unquote(parts.path) + " " + link.text_content()).lower()
            for kind, words in PAGE_KEYWORDS.items():
                if kind not in found and any(word in haystack for word in words):
                    found[kind] = url
                    break
        return {kind: found[kind] for kind in PAGE_KEYWORDS if kind in found}

    def _get(self, url: str, stats: Counter) -> str:
        cached = self.cache.get(url)
        if cached is not None:
            stats["cache"] += 1
            return cached
        stats["network"] += 1
        try:
            response = self.client.get(url)
        except (httpx.HTTPError, httpx.InvalidURL):
            text = ""
        else:
            is_text = response.headers.get("content-type", "").startswith("text/")
            if response.status_code != 200 or not is_text:
                text = ""
            elif response.charset_encoding:
                text = response.text
            else:
                # Кодировка не указана в заголовке — у русских сайтов это часто windows-1251 в <meta>.
                text = decode_file(response.content)
        # Неудачи тоже кэшируются, чтобы повторный прогон не ходил в сеть.
        # Сбросить — удалить файл кэша.
        self.cache.put(url, text)
        return text
