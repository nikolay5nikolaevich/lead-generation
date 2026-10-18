from leadgen.graph.log import log
from leadgen.llm.fake import FakeLLM
from leadgen.state import CompanyState

llm = FakeLLM()


# Статус READY ставит не этот узел, а verify_draft, когда письмо прошло проверку.
def draft_email(state: CompanyState) -> dict:
    rewrite = bool(state["unsupported_claims"])
    draft, calls = llm.draft_email(
        state["domain"], state["facts"], state["draft"], state["unsupported_claims"], state["icp_text"]
    )
    log(state["domain"], "draft_email, переписывание" if rewrite else "draft_email", calls)
    return {"draft": draft, "budget": {"llm_calls": calls}}
