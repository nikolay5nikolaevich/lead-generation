from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send, interrupt

from leadgen.config import OUTPUT_CSV
from leadgen.export.csv import write_leads
from leadgen.graph.company import build_company_graph
from leadgen.graph.log import log
from leadgen.graph.nodes.search import normalize_domains, plan_queries, search
from leadgen.graph.retry import LLM_RETRY, NETWORK_RETRY
from leadgen.models import Lead, Status
from leadgen.state import OuterState


# dispatch — не узел, а развилка на ребре: состояние не меняет, только решает,
# куда идти дальше. Send("process_company", {...}) значит «запусти узел process_company
# вот с таким входом». Сколько Send в списке — столько параллельных веток.
# Пустой список Send = «никуда не идти»: граф закончился бы, не дойдя до export.
# Поэтому без доменов возвращаем имя узла строкой — «иди прямо сюда».
def dispatch(state: OuterState) -> list[Send] | str:
    if not state["domains"]:
        return "export"
    return [Send("process_company", {"domain": domain, "icp_text": state["icp_text"]}) for domain in state["domains"]]


def route_after_normalize(state: OuterState) -> list[Send] | str:
    if state.get("review_domains"):
        return "review_domains"
    return dispatch(state)


# interrupt() останавливает граф и отдаёт список доменов наружу: invoke возвращается
# с ключом __interrupt__. Позиция сохраняется в чекпоинте, поэтому продолжить можно
# из другого процесса. Command(resume=список) перезапускает узел с начала, и тогда
# interrupt() не останавливает граф, а возвращает этот список.
def review_domains(state: OuterState) -> dict:
    return {"domains": interrupt(state["domains"])}


company_graph = build_company_graph()


# Мост между двумя графами. На вход — то, что положили в Send: {"domain": ..., "icp_text": ...}.
# Подграф запускается как обычная функция со своим чистым состоянием CompanyState,
# а из его итога мы собираем один Lead и отдаём во внешний граф.
def process_company(branch_input: dict) -> dict:
    domain = branch_input["domain"]
    result = company_graph.invoke({
        "domain": domain,
        "icp_text": branch_input["icp_text"],
        "pages": {},
        "facts": [],
        "facts_dropped": 0,
        "score": None,
        "email": None,
        "draft": "",
        "unsupported_claims": [],
        "status": Status.PENDING,
        "budget": {},
    })
    log(domain, result["status"])
    lead = Lead(
        domain=domain,
        facts=result["facts"],
        facts_dropped=result["facts_dropped"],
        score=result["score"],
        email=result["email"],
        draft=result["draft"],
        status=result["status"],
    )
    # Список из одного лида. Reducer operator.add приклеит его к leads,
    # а не заменит им то, что туда уже записали другие ветки. Расход ветки
    # так же прибавится к общему budget.
    return {"leads": [lead], "budget": result["budget"]}


def export(state: OuterState) -> dict:
    write_leads(state["leads"], OUTPUT_CSV)
    return {}  # в состоянии ничего не меняем


def build_graph(checkpointer: BaseCheckpointSaver | None = None):
    # StateGraph получает схему состояния: по ней он знает ключи и их reducer'ы.
    builder = StateGraph(OuterState)

    builder.add_node("plan_queries", plan_queries, retry_policy=LLM_RETRY)
    builder.add_node("search", search, retry_policy=NETWORK_RETRY)
    builder.add_node("normalize_domains", normalize_domains)
    builder.add_node("review_domains", review_domains)
    builder.add_node("process_company", process_company)
    builder.add_node("export", export)

    builder.add_edge(START, "plan_queries")
    builder.add_edge("plan_queries", "search")
    builder.add_edge("search", "normalize_domains")
    # Условное ребро: после normalize_domains вызвать dispatch и пойти туда, куда
    # он укажет. Третий аргумент — куда он вообще может указать (нужно для картинки графа).
    builder.add_conditional_edges("normalize_domains", route_after_normalize, ["review_domains", "process_company", "export"])
    builder.add_conditional_edges("review_domains", dispatch, ["process_company", "export"])
    # export ждёт, пока завершатся ВСЕ ветки process_company, и запускается один раз.
    builder.add_edge("process_company", "export")
    builder.add_edge("export", END)

    # compile() проверяет граф (нет ли узлов без входа, опечаток в именах)
    # и превращает описание в объект, который можно запустить.
    # С чекпоинтером состояние сохраняется после каждого шага, а результат каждой готовой
    # ветки — сразу, как она закончилась. После падения invoke(None, тот же thread_id)
    # запускает только то, что не успело закончиться.
    return builder.compile(checkpointer=checkpointer)
