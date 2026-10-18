from leadgen.config import NEED_MIN_RATING, RUBRIC_WEIGHTS, SCORE_THRESHOLD
from leadgen.graph.log import log
from leadgen.llm.fake import FakeLLM
from leadgen.models import Score, Status
from leadgen.state import CompanyState

llm = FakeLLM()


def score(state: CompanyState) -> dict:
    criteria, calls = llm.rate_criteria(state["domain"], state["facts"], state["icp_text"])
    # Модель ставит по каждому критерию 0–3, итог 0–100 считает Python.
    total = round(sum(RUBRIC_WEIGHTS[item.criterion] * item.rating / 3 for item in criteria))
    log(state["domain"], f"score {total}", calls)
    result = {"score": Score(criteria=criteria, total=total), "budget": {"llm_calls": calls}}
    need = next(item.rating for item in criteria if item.criterion == "need")
    if total < SCORE_THRESHOLD or need < NEED_MIN_RATING:
        result["status"] = Status.REJECTED
    return result
