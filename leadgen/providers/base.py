from typing import Protocol

from leadgen.models import EmailHit


class SearchProvider(Protocol):
    def search(self, query: str, max_results: int) -> list[str]:
        """Вернуть URL из поисковой выдачи."""
        ...


class PageFetcher(Protocol):
    def fetch(self, domain: str) -> dict[str, str]:
        """Вернуть текст ключевых страниц сайта: {url: текст}. Нет текста — пустой словарь."""
        ...


class EmailFinder(Protocol):
    # True — find() обращается к внешнему сервису с квотой, запрос идёт в budget.email_lookups.
    external: bool

    def find(self, domain: str) -> list[EmailHit]:
        """Вернуть найденные адреса домена. Ничего не найдено — пустой список."""
        ...
