from langgraph.graph import END, START, StateGraph

from leadgen.graph.nodes.draft import draft_email
from leadgen.graph.nodes.email import find_email
from leadgen.graph.nodes.facts import extract_facts
from leadgen.graph.nodes.fetch import fetch_pages
from leadgen.graph.nodes.score import score
from leadgen.graph.nodes.validate import validate_facts
from leadgen.graph.nodes.verify_draft import verify_draft
from leadgen.graph.retry import LLM_RETRY, NETWORK_RETRY
from leadgen.models import Status
from leadgen.state import CompanyState


# Маршрутизаторы. Узел записывает в состояние, что случилось (status),
# маршрутизатор читает это и возвращает имя следующего узла — или END,
# и тогда ветка этой компании заканчивается прямо здесь.
def route_after_fetch(state: CompanyState) -> str:
    if state["status"] == Status.NO_DATA:
        return END
    return "extract_facts"


def route_after_score(state: CompanyState) -> str:
    if state["status"] == Status.REJECTED:
        return END
    return "find_email"


def route_after_email(state: CompanyState) -> str:
    if state["status"] == Status.NO_EMAIL:
        return END
    return "draft_email"


# PENDING после проверки — в письме нашлись утверждения без фактов, и его ещё не переписывали.
def route_after_verify(state: CompanyState) -> str:
    if state["status"] == Status.PENDING:
        return "draft_email"
    return END


def build_company_graph():
    # Отдельный граф со своим состоянием CompanyState. Про OuterState он не знает.
    builder = StateGraph(CompanyState)

    builder.add_node("fetch_pages", fetch_pages, retry_policy=NETWORK_RETRY)
    builder.add_node("extract_facts", extract_facts, retry_policy=LLM_RETRY)
    builder.add_node("validate_facts", validate_facts)
    builder.add_node("score", score, retry_policy=LLM_RETRY)
    builder.add_node("find_email", find_email, retry_policy=NETWORK_RETRY)
    builder.add_node("draft_email", draft_email, retry_policy=LLM_RETRY)
    builder.add_node("verify_draft", verify_draft, retry_policy=LLM_RETRY)

    builder.add_edge(START, "fetch_pages")
    builder.add_conditional_edges("fetch_pages", route_after_fetch, ["extract_facts", END])
    builder.add_edge("extract_facts", "validate_facts")
    builder.add_edge("validate_facts", "score")
    builder.add_conditional_edges("score", route_after_score, ["find_email", END])
    builder.add_conditional_edges("find_email", route_after_email, ["draft_email", END])
    builder.add_edge("draft_email", "verify_draft")
    builder.add_conditional_edges("verify_draft", route_after_verify, ["draft_email", END])

    # Чекпоинтер не передаём: подграф, запущенный внутри узла внешнего графа, берёт чекпоинтер
    # внешнего и сохраняет каждый свой шаг под именем ветки. После падения ветка продолжается
    # с упавшего узла: fetch_pages и extract_facts, успевшие отработать, не повторяются.
    return builder.compile()
