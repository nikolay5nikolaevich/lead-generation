from leadgen.graph.log import log
from leadgen.llm.fake import FakeLLM
from leadgen.models import Status
from leadgen.state import CompanyState

llm = FakeLLM()


# Модель выписывает утверждения письма и ссылается на номера фактов, а решает код:
# утверждение без ссылки или со ссылкой на несуществующий номер — без опоры.
def verify_draft(state: CompanyState) -> dict:
    facts = state["facts"]
    claims, calls = llm.extract_claims(state["domain"], state["draft"], facts)
    unsupported = [
        item.claim for item in claims
        if not item.fact_ids or any(not 1 <= number <= len(facts) for number in item.fact_ids)
    ]
    for claim in unsupported:
        log(state["domain"], f"утверждение без факта: «{claim}»")
    log(state["domain"], f"verify_draft, утверждений {len(claims)}, без опоры {len(unsupported)}", calls)

    result = {"unsupported_claims": unsupported, "budget": {"llm_calls": calls}}
    if not unsupported:
        result["status"] = Status.READY
    elif state["unsupported_claims"]:
        # Письмо уже переписывали по прошлой проверке — второй раз не переписываем.
        result["status"] = Status.DRAFT_UNVERIFIED
    # Иначе статус остаётся PENDING, и маршрутизатор отправляет письмо на переписывание.
    return result
