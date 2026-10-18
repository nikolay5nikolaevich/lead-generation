"""Метрики качества на golden set: python evals/run_eval.py

Домены golden set проходят тот же путь, что в прогоне, кроме поиска: нормализация
и стоп-лист, затем подграф компании. Поиск пропускаем — выдача Tavily меняется от раза
к разу, а размечены только эти домены. Неизменившиеся промпты берутся из кэша LLM.
"""

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlsplit

import typer
from dotenv import load_dotenv

from leadgen.cli import use_llm, use_real_providers
from leadgen.config import DB_PATH, MAX_CONCURRENCY, PROJECT_ROOT
from leadgen.export.csv import write_leads
from leadgen.graph.nodes.search import normalize_domains
from leadgen.graph.outer import process_company
from leadgen.llm.claude import ClaudeLLM
from leadgen.llm.client import BudgetExhausted, ClaudeClient
from leadgen.llm.prompts import SYSTEM_PROMPT
from leadgen.models import Lead, Status
from leadgen.storage.llm_cache import LlmCache

EVALS_DIR = Path(__file__).parent
# Прошли стоп-лист и скоринг: в прогоне агент выдал бы их как лиды.
FOUND = {Status.READY, Status.DRAFT_UNVERIFIED, Status.NO_EMAIL}
LABELS = {True: "да", False: "нет", None: "?"}
FREE_MAIL = {"yandex.ru", "ya.ru", "mail.ru", "bk.ru", "list.ru", "inbox.ru", "rambler.ru", "gmail.com"}


# Для метрики SPEC §10 «ролевой или корпоративный»: ролевой адрес или ящик компании на бесплатной
# почте, опубликованный на её сайте (решение владельца). Персональные адреса от Hunter не считаются.
def company_email(lead: Lead) -> bool:
    email = lead.email
    if email is None:
        return False
    host = urlsplit(email.source).hostname or ""  # у адресов от Hunter источник «hunter.io: …», хоста нет
    on_site = host == lead.domain or host.endswith("." + lead.domain)
    return email.kind == "role" or (on_site and email.address.split("@")[1] in FREE_MAIL)


def share(part: int, whole: int) -> str:
    return f"{part}/{whole} = {part / whole:.0%}" if whole else "нет данных"


def main(max_llm_calls: int = typer.Option(150, "--max-llm-calls", help="Сколько вызовов модели можно сделать.")):
    load_dotenv(PROJECT_ROOT / ".env")
    golden = json.loads((EVALS_DIR / "golden_set.json").read_text(encoding="utf-8"))
    icp_text = (PROJECT_ROOT / golden["icp"]).read_text(encoding="utf-8")
    labels = {item["domain"]: item["fits_icp"] for item in golden["companies"]}

    use_real_providers()
    client = ClaudeClient(LlmCache(DB_PATH), SYSTEM_PROMPT, max_llm_calls)
    use_llm(ClaudeLLM(client))

    domains = normalize_domains({"domains": list(labels), "limit": len(labels)})["domains"]
    try:
        with ThreadPoolExecutor(MAX_CONCURRENCY) as pool:
            results = pool.map(lambda domain: process_company({"domain": domain, "icp_text": icp_text}), domains)
            leads = {result["leads"][0].domain: result["leads"][0] for result in results}
    except BudgetExhausted as error:
        print(f"Остановлено: {error}. Готовые ответы в кэше, повторный запуск их не потратит.")
        raise typer.Exit(1)
    write_leads(list(leads.values()), EVALS_DIR / "eval_out.csv")

    print(f"\n{'домен':24} {'ICP':4} {'статус':17} {'балл':>4} {'факты':>7}  email")
    for domain, label in labels.items():
        lead = leads.get(domain)
        if lead is None:
            print(f"{domain:24} {LABELS[label]:4} стоп-лист")
            continue
        score = lead.score.total if lead.score else ""
        facts = f"{len(lead.facts)}-{lead.facts_dropped}" if lead.facts_dropped else str(len(lead.facts))
        email = f"{lead.email.kind} {lead.email.address}" if lead.email else ""
        print(f"{domain:24} {LABELS[label]:4} {lead.status:17} {score:>4} {facts:>7}  {email}")

    labeled = [domain for domain, label in labels.items() if label is not None]
    fits = [domain for domain in labeled if labels[domain]]
    found_leads = [lead for lead in leads.values() if lead.status in FOUND]
    found = [lead.domain for lead in found_leads if labels[lead.domain] is not None]
    missed = [domain for domain in fits if domain not in found]
    drafts = [lead for lead in found_leads if lead.draft]

    print()
    if len(labeled) < len(labels):
        print(f"Не размечено {len(labels) - len(labeled)} из {len(labels)}: они не входят в метрики.")
    print(f"Подходят под ICP среди всех доменов golden set (выдача поиска): {share(len(fits), len(labeled))}")
    print(f"Релевантных среди найденных (прошли стоп-лист и скоринг): {share(sum(labels[d] for d in found), len(found))}  цель ≥70%")
    print(f"Подходящие, которые агент отсеял: {', '.join(missed) or 'нет'}")
    print(f"Лидов с ролевым email или ящиком компании на бесплатной почте: {share(sum(map(company_email, found_leads)), len(found_leads))}  цель ≥60%")
    print(f"Письма прошли verify_draft: {share(sum(lead.status == Status.READY for lead in drafts), len(drafts))}")
    print(f"Вызовов модели: {client.calls}, из кэша {client.cache_hits}. Строки лидов: {EVALS_DIR / 'eval_out.csv'}")


if __name__ == "__main__":
    typer.run(main)
