import os
import time
import uuid
from pathlib import Path

import typer
from dotenv import load_dotenv
from langgraph.types import Command

from leadgen.config import DB_PATH, DEFAULT_LIMIT, DEFAULT_MAX_LLM_CALLS, MAX_CONCURRENCY, OUTPUT_CSV, PROJECT_ROOT
from leadgen.export.csv import write_leads
from leadgen.graph.nodes import draft as draft_node
from leadgen.graph.nodes import email as email_node
from leadgen.graph.nodes import facts as facts_node
from leadgen.graph.nodes import fetch as fetch_node
from leadgen.graph.nodes import score as score_node
from leadgen.graph.nodes import search as search_node
from leadgen.graph.nodes import verify_draft as verify_node
from leadgen.graph.outer import build_graph
from leadgen.llm.claude import ClaudeLLM
from leadgen.llm.client import BudgetExhausted, ClaudeClient
from leadgen.llm.fake import FakeLLM
from leadgen.llm.prompts import SYSTEM_PROMPT
from leadgen.models import Lead, Status
from leadgen.providers.http_fetcher import HttpPageFetcher
from leadgen.providers.hunter import HunterEmailFinder
from leadgen.providers.site_emails import SiteEmailFinder
from leadgen.providers.tavily import TavilySearchProvider
from leadgen.storage.cache import PageCache
from leadgen.storage.checkpoint import open_checkpointer
from leadgen.storage.llm_cache import LlmCache

app = typer.Typer()


@app.callback()
def main():
    """Агент лидогенерации."""
    load_dotenv(PROJECT_ROOT / ".env")


# Узлы берут провайдеров из переменных своего модуля, по умолчанию там фейки.
# Без --offline подменяем их реальными до запуска графа; сам граф об этом не знает.
def use_real_providers() -> HttpPageFetcher:
    fetcher = HttpPageFetcher(PageCache(DB_PATH))
    search_node.search_provider = TavilySearchProvider(os.environ["TAVILY_API_KEY"])
    fetch_node.page_fetcher = fetcher
    email_node.email_finders = [SiteEmailFinder(fetcher), HunterEmailFinder(os.environ.get("HUNTER_API_KEY", ""))]
    return fetcher


# Один объект LLM на все узлы: у него общий на все ветки счётчик и лимит вызовов.
def use_llm(llm: ClaudeLLM | FakeLLM) -> None:
    for node in (search_node, facts_node, score_node, draft_node, verify_node):
        node.llm = llm


# Прогон остановлен посреди обработки компаний. get_state уже включает в leads готовые ветки
# незавершённого шага, остальные компании пишем в CSV со статусом BUDGET_STOP.
def write_stopped_leads(graph, config: dict) -> None:
    snapshot = graph.get_state(config)
    leads = snapshot.values.get("leads", [])
    done = {lead.domain for lead in leads}
    leads += [Lead(domain=domain, status=Status.BUDGET_STOP) for domain in snapshot.values.get("domains", []) if domain not in done]
    write_leads(leads, OUTPUT_CSV)


# Человек вычёркивает мусор из найденных доменов. Возвращает список, с которым граф продолжит.
def ask_review(domains: list[str]) -> list[str]:
    for number, domain in enumerate(domains, 1):
        print(f"{number:3}. {domain}")
    while True:
        answer = typer.prompt("Номера доменов, которые убрать, через пробел (Enter — оставить все)", default="", show_default=False)
        numbers = answer.replace(",", " ").split()
        if all(number.isdigit() and 1 <= int(number) <= len(domains) for number in numbers):
            break
        print(f"Нужны номера от 1 до {len(domains)}")
    removed = {int(number) for number in numbers}
    print(f"Убрано {len(removed)}, в обработку {len(domains) - len(removed)}")
    return [domain for number, domain in enumerate(domains, 1) if number not in removed]


@app.command()
def run(
    offline: bool = typer.Option(False, "--offline", help="Фикстуры и фейковый LLM, без сети."),
    limit: int = typer.Option(DEFAULT_LIMIT, "--limit", help="Сколько компаний обработать."),
    icp: Path | None = typer.Option(None, "--icp", help="Файл с текстом ICP. Без --offline обязателен."),
    thread_id: str | None = typer.Option(None, "--thread-id", help="Идентификатор прогона в чекпоинтах. По умолчанию новый."),
    resume: bool = typer.Option(False, "--resume", help="Продолжить прогон --thread-id с места остановки."),
    review: bool = typer.Option(False, "--review-domains", help="Пауза, чтобы вычеркнуть лишние домены до обработки."),
    max_llm_calls: int = typer.Option(
        DEFAULT_MAX_LLM_CALLS, "--max-llm-calls", help="Сколько вызовов модели можно сделать за этот запуск."
    ),
):
    if resume and thread_id is None:
        raise typer.BadParameter("для --resume нужен --thread-id", param_hint="--thread-id")
    # При --resume текст ICP уже лежит в чекпоинте.
    if not offline and icp is None and not resume:
        raise typer.BadParameter("без --offline нужен файл ICP", param_hint="--icp")
    # Фейковому LLM текст ICP не нужен: ответы у него из фикстур.
    icp_text = icp.read_text(encoding="utf-8") if icp else ""
    fetcher = None if offline else use_real_providers()
    client = None
    if offline:
        use_llm(FakeLLM(max_llm_calls))
    else:
        client = ClaudeClient(LlmCache(DB_PATH), SYSTEM_PROMPT, max_llm_calls)
        use_llm(ClaudeLLM(client))

    graph = build_graph(open_checkpointer(DB_PATH))
    thread_id = thread_id or uuid.uuid4().hex[:8]
    # thread_id — имя прогона в чекпоинтах. max_concurrency — сколько веток работает одновременно.
    config = {"configurable": {"thread_id": thread_id}, "max_concurrency": MAX_CONCURRENCY}
    saved = graph.get_state(config)
    if resume and not saved.next:
        raise typer.BadParameter(f"прогон {thread_id} не найден или уже завершён", param_hint="--thread-id")
    if not resume and saved.values:
        raise typer.BadParameter(f"прогон {thread_id} уже есть: продолжить — --resume, новый — другой id", param_hint="--thread-id")
    resume_command = f"leadgen run --resume --thread-id {thread_id}" + (" --offline" if offline else "")
    print(f"thread_id: {thread_id}  (продолжить после остановки: {resume_command})")

    started = time.time()
    try:
        # Начальное состояние — только то, что известно до запуска, остальное заполнят узлы.
        # None вместо состояния — продолжить сохранённый прогон с места остановки.
        final_state = graph.invoke(
            None if resume else {"icp_text": icp_text, "limit": limit, "review_domains": review}, config
        )
        # Граф встал на interrupt() в review_domains. При --resume с паузы invoke(None) перезапускает
        # этот узел, и он снова встаёт на паузу — поэтому список показывается и после перезапуска.
        if "__interrupt__" in final_state:
            print(f"Пауза на ревью доменов сохранена. Закрыть и вернуться позже: {resume_command}")
            kept = ask_review(final_state["__interrupt__"][0].value)
            final_state = graph.invoke(Command(resume=kept), config)
    except BudgetExhausted as error:
        final_state = None
        write_stopped_leads(graph, config)
        print(f"BUDGET_STOP: {error}. Продолжить: {resume_command}")

    if fetcher:
        print(f"Запросы к сайтам: из сети {fetcher.stats['network']}, из кэша {fetcher.stats['cache']}")
    if client:
        print(f"Вызовы модели за запуск: {client.calls}, ответов из кэша {client.cache_hits}")
    if final_state is None:
        print(f"Остановлено через {time.time() - started:.1f} с, файл {OUTPUT_CSV}")
        return
    budget = final_state["budget"]
    print(f"Отсеяны стоп-листом: {', '.join(final_state['rejected_domains'])}")
    print(
        f"Итого за прогон: вызовов модели {budget['llm_calls']}, запросов к поиску {budget['search_requests']}, "
        f"к Hunter {budget['email_lookups']}"
    )
    print(f"Готово за {time.time() - started:.1f} с: строк {len(final_state['leads'])}, файл {OUTPUT_CSV}")
