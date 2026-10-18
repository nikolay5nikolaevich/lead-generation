from leadgen.graph.log import log
from leadgen.models import Fact
from leadgen.state import CompanyState

# Типографские кавычки модель при копировании часто заменяет прямыми и наоборот.
QUOTES = str.maketrans({"«": '"', "»": '"', "„": '"', "“": '"', "”": '"', "‘": "'", "’": "'", "‚": "'"})


# Регистр, кавычки и пробелы. split() без аргумента режет по любым пробельным символам,
# включая неразрывный, и склеивает их серии в один пробел.
def normalize(text: str) -> str:
    return " ".join(text.translate(QUOTES).casefold().split())


# Почему факт не прошёл, или None, если прошёл. Цитата ищется только на той странице,
# на которую ссылается факт: pages — тексты, загруженные fetch_pages, а не слова модели.
def rejection_reason(fact: Fact, pages: dict[str, str]) -> str | None:
    page = pages.get(str(fact.source_url))
    if page is None:
        return "страница не загружалась"
    quote = normalize(fact.quote)
    if not quote or quote not in normalize(page):
        return "цитаты нет на странице"
    return None


def validate_facts(state: CompanyState) -> dict:
    kept = []
    for fact in state["facts"]:
        reason = rejection_reason(fact, state["pages"])
        if reason is None:
            kept.append(fact)
        else:
            log(state["domain"], f"отброшен факт {fact.kind}, {reason}: «{fact.quote}» ({fact.source_url})")
    dropped = len(state["facts"]) - len(kept)
    log(state["domain"], f"validate_facts, прошли {len(kept)}, отброшено {dropped}")
    return {"facts": kept, "facts_dropped": dropped}
