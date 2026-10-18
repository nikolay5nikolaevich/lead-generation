from leadgen.graph.log import log
from leadgen.models import Status
from leadgen.providers.fake import FakeEmailFinder
from leadgen.state import CompanyState

# Источники по приоритету: следующий спрашиваем, только если предыдущий ничего не нашёл.
email_finders = [FakeEmailFinder()]


def find_email(state: CompanyState) -> dict:
    lookups = 0  # запросы к внешнему сервису с квотой (Hunter)
    for finder in email_finders:
        hits = finder.find(state["domain"])
        if finder.external:
            lookups += 1
        if hits:
            role_hits = [hit for hit in hits if hit.kind == "role"]
            email = role_hits[0] if role_hits else hits[0]
            log(state["domain"], f"find_email, {email.address}")
            return {"email": email, "budget": {"email_lookups": lookups}}
    log(state["domain"], "find_email, адрес не найден")
    return {"status": Status.NO_EMAIL, "budget": {"email_lookups": lookups}}
