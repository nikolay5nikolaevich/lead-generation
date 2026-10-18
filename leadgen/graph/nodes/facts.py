from leadgen.graph.log import log
from leadgen.llm.fake import FakeLLM
from leadgen.state import CompanyState

llm = FakeLLM()


def extract_facts(state: CompanyState) -> dict:
    facts, calls = llm.extract_facts(state["domain"], state["pages"], state["icp_text"])
    log(state["domain"], f"extract_facts, фактов {len(facts)}", calls)
    return {"facts": facts, "budget": {"llm_calls": calls}}
