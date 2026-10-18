import operator
from typing import Annotated, TypedDict

from leadgen.models import EmailHit, Fact, Lead, Score, Status


# Модель работает по подписке Claude Pro, поэтому расход считается в штуках вызовов,
# а не в долларах: у подписки нет счёта, есть лимит использования.
# total=False: узел возвращает только те счётчики, которые у него выросли.
class Budget(TypedDict, total=False):
    llm_calls: int  # настоящие вызовы модели, ответы из кэша не считаются
    search_requests: int  # запросы к Tavily
    email_lookups: int  # запросы к Hunter


# Reducer для budget: узел возвращает прирост счётчиков, а не новое значение,
# и LangGraph складывает его с накопленным. Так в budget могут писать параллельные ветки
# и итог за прогон попадает в чекпоинт вместе с остальным состоянием.
def add_budget(left: Budget, right: Budget) -> Budget:
    return {key: left.get(key, 0) + right.get(key, 0) for key in Budget.__annotations__}


# Состояние внешнего графа: одно на весь запуск.
# Это TypedDict, а не Pydantic-модель: LangGraph хранит состояние как обычный словарь
# и сам склеивает в него обновления от узлов. Ему нужно знать ключи и их типы,
# проверять значения на каждом шаге не нужно.
class OuterState(TypedDict):
    icp_text: str
    limit: int
    review_domains: bool  # пауза на ревью доменов; лежит в чекпоинте, при --resume флаг не нужен
    queries: list[str]
    domains: list[str]
    # Annotated = тип + приклеенная к нему информация. Тип здесь list[Lead],
    # а operator.add — функция, которую LangGraph вызывает, чтобы
    # склеить старое значение ключа с новым: старый_список + новый_список.
    # Без неё параллельные ветки не смогут одновременно писать в leads.
    leads: Annotated[list[Lead], operator.add]
    rejected_domains: Annotated[list[str], operator.add]
    budget: Annotated[Budget, add_budget]


# Состояние одной компании внутри подграфа. У каждой ветки своё:
# ветки идут параллельно и не должны видеть и перезаписывать чужие данные.
class CompanyState(TypedDict):
    domain: str
    icp_text: str  # нужен модели для скоринга и письма
    pages: dict[str, str]  # url -> текст страницы, чтобы у каждого фрагмента был источник
    facts: list[Fact]
    facts_dropped: int  # сколько фактов отбросил validate_facts
    score: Score | None
    email: EmailHit | None
    draft: str
    # Утверждения письма без опоры на факты, их нашёл verify_draft. Непустой список при входе
    # в draft_email значит «перепиши», при входе в verify_draft — «письмо уже переписывали».
    unsupported_claims: list[str]
    status: Status
    budget: Annotated[Budget, add_budget]  # расход этой ветки, уходит в OuterState.budget
