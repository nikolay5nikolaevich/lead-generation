import json
import re
import threading

from leadgen.config import FIXTURES_DIR
from leadgen.llm.client import BudgetExhausted
from leadgen.llm.prompts import Claim
from leadgen.models import Fact, FactKind, ScoreCriterion


# Ответы из фикстур. Текст ICP принимает ради одинаковых методов с ClaudeLLM, но не читает.
# Каждый ответ считается вызовом модели и подчиняется лимиту, как у ClaudeClient:
# так бюджет и BUDGET_STOP проверяются без сети.
class FakeLLM:
    def __init__(self, max_calls: int | None = None):
        self.answers = json.loads((FIXTURES_DIR / "llm_answers.json").read_text(encoding="utf-8"))
        self.max_calls = max_calls
        self.calls = 0
        self._lock = threading.Lock()

    def _call(self) -> int:
        with self._lock:
            if self.max_calls is not None and self.calls >= self.max_calls:
                raise BudgetExhausted(f"выбран лимит вызовов модели на запуск: {self.max_calls}")
            self.calls += 1
        return 1

    def plan_queries(self, icp_text: str, count: int) -> tuple[list[str], int]:
        return self.answers["queries"], self._call()

    def extract_facts(self, domain: str, pages: dict[str, str], icp_text: str) -> tuple[list[Fact], int]:
        company = self.answers["companies"].get(domain, {})
        return [Fact.model_validate(item) for item in company.get("facts", [])], self._call()

    def rate_criteria(self, domain: str, facts: list[Fact], icp_text: str) -> tuple[list[ScoreCriterion], int]:
        company = self.answers["companies"].get(domain, {})
        return [ScoreCriterion.model_validate(item) for item in company.get("criteria", [])], self._call()

    def draft_email(
        self, domain: str, facts: list[Fact], previous_draft: str, unsupported_claims: list[str], icp_text: str
    ) -> tuple[str, int]:
        hooks = [fact for fact in facts if fact.kind == FactKind.HOOK] or facts
        draft = (
            "Здравствуйте!\n\n"
            f"Прочитали на вашем сайте: «{hooks[0].quote}». "
            "Мы помогаем складам автоматизировать приёмку и инвентаризацию. "
            "Если тема актуальна, давайте созвонимся на 15 минут на этой неделе?"
        )
        return draft, self._call()

    # Утверждение — каждая цитата в «ёлочках» из письма, опора — факт с той же цитатой.
    def extract_claims(self, domain: str, draft: str, facts: list[Fact]) -> tuple[list[Claim], int]:
        claims = [
            Claim(claim=quoted, fact_ids=[number for number, fact in enumerate(facts, 1) if fact.quote == quoted])
            for quoted in re.findall(r"«([^»]+)»", draft)
        ]
        return claims, self._call()
