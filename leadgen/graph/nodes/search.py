import math

import tldextract

from leadgen.config import SEARCH_RESULTS_PER_QUERY, STOP_DOMAINS
from leadgen.llm.fake import FakeLLM
from leadgen.providers.fake import FakeSearchProvider
from leadgen.state import OuterState

llm = FakeLLM()
search_provider = FakeSearchProvider()

# suffix_list_urls=() — список доменных зон берётся из копии внутри библиотеки, без сети.
# include_psl_private_domains=True — spb.ru и msk.ru тоже считаются зонами:
# firma.spb.ru и shop.spb.ru — две разные компании, а не одна spb.ru.
extract_domain = tldextract.TLDExtract(suffix_list_urls=(), include_psl_private_domains=True)


# Узел получает всё состояние, а возвращает только те ключи, которые меняет.
def plan_queries(state: OuterState) -> dict:
    # Запрос даёт до SEARCH_RESULTS_PER_QUERY адресов, после дублей и стоп-листа остаётся
    # примерно половина: на каждые 10 компаний лимита — ещё один запрос.
    count = max(3, math.ceil(state["limit"] / 10))
    queries, calls = llm.plan_queries(state["icp_text"], count)
    return {"queries": queries, "budget": {"llm_calls": calls}}


def search(state: OuterState) -> dict:
    urls = []
    for query in state["queries"]:
        urls += search_provider.search(query, SEARCH_RESULTS_PER_QUERY)
    # Сырые URL кладём в domains, следующий узел заменит их чистыми доменами.
    return {"domains": urls, "budget": {"search_requests": len(state["queries"])}}


def normalize_domains(state: OuterState) -> dict:
    domains = []
    rejected_domains = []
    for url in state["domains"]:
        domain = extract_domain(url).top_domain_under_public_suffix.lower()
        if domain in STOP_DOMAINS:
            if domain not in rejected_domains:
                rejected_domains.append(domain)
            continue
        if not domain or domain in domains:
            continue
        domains.append(domain)
    return {"domains": domains[: state["limit"]], "rejected_domains": rejected_domains}
