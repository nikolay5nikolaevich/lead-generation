import pytest

from leadgen.config import RUBRIC_WEIGHTS
from leadgen.llm.client import BudgetExhausted
from leadgen.llm.fake import FakeLLM
from leadgen.providers.fake import FakeEmailFinder, FakePageFetcher, FakeSearchProvider
from leadgen.state import add_budget


def test_search_returns_urls():
    urls = FakeSearchProvider().search("складская логистика", max_results=10)
    assert urls
    assert all(url.startswith("http") for url in urls)


def test_search_respects_max_results():
    assert len(FakeSearchProvider().search("что угодно", max_results=2)) == 2


def test_normal_site_has_text():
    pages = FakePageFetcher().fetch("severtrans-logistic.ru")
    assert "https://severtrans-logistic.ru/" in pages
    assert "180 сотрудников" in pages["https://severtrans-logistic.ru/about"]


def test_js_only_site_has_no_text():
    assert FakePageFetcher().fetch("vektor-cargo.ru") == {}


def test_unknown_site_has_no_text():
    assert FakePageFetcher().fetch("no-such-site.ru") == {}


def test_email_finder():
    hits = FakeEmailFinder().find("severtrans-logistic.ru")
    assert hits[0].kind == "role"
    assert FakeEmailFinder().find("vektor-cargo.ru") == []


def test_fake_llm_quotes_exist_on_pages():
    # Если фикстуры разъедутся, валидатор цитат (этап 7) начнёт отбрасывать факты.
    llm = FakeLLM()
    fetcher = FakePageFetcher()
    for domain in ["severtrans-logistic.ru", "pekarnya-kolosok.ru"]:
        pages = fetcher.fetch(domain)
        facts, _ = llm.extract_facts(domain, pages, icp_text="")
        for fact in facts:
            assert fact.quote in pages[str(fact.source_url)]


def test_fake_llm_rates_every_rubric_criterion():
    criteria, _ = FakeLLM().rate_criteria("severtrans-logistic.ru", facts=[], icp_text="")
    assert {item.criterion for item in criteria} == set(RUBRIC_WEIGHTS)


def test_fake_llm_draft_uses_fact_quote():
    llm = FakeLLM()
    facts, _ = llm.extract_facts("severtrans-logistic.ru", pages={}, icp_text="")
    draft, _ = llm.draft_email("severtrans-logistic.ru", facts, "", [], icp_text="")
    assert "переводим учёт остатков" in draft


def test_fake_llm_stops_at_call_limit():
    llm = FakeLLM(max_calls=2)
    assert llm.plan_queries(icp_text="", count=3)[1] == 1
    llm.plan_queries(icp_text="", count=3)
    with pytest.raises(BudgetExhausted):
        llm.plan_queries(icp_text="", count=3)


def test_add_budget_sums_partial_updates():
    total = add_budget({}, {"llm_calls": 2})
    total = add_budget(total, {"llm_calls": 1, "email_lookups": 1})
    assert total == {"llm_calls": 3, "search_requests": 0, "email_lookups": 1}
