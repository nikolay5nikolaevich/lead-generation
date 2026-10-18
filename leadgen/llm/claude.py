from leadgen.config import RUBRIC_WEIGHTS
from leadgen.llm import prompts
from leadgen.llm.client import ClaudeClient
from leadgen.models import Fact, ScoreCriterion


# Те же методы, что у FakeLLM: узлы не знают, какая модель у них внутри.
# Каждый метод возвращает пару (ответ, число вызовов модели) — узел кладёт второе в budget.
class ClaudeLLM:
    def __init__(self, client: ClaudeClient):
        self.client = client

    def plan_queries(self, icp_text: str, count: int) -> tuple[list[str], int]:
        answer, calls = self.client.ask(prompts.plan_queries_prompt(icp_text, count), prompts.SearchQueries)
        return answer.queries, calls

    def extract_facts(self, domain: str, pages: dict[str, str], icp_text: str) -> tuple[list[Fact], int]:
        answer, calls = self.client.ask(prompts.extract_facts_prompt(icp_text, domain, pages), prompts.ExtractedFacts)
        return answer.facts, calls

    def rate_criteria(self, domain: str, facts: list[Fact], icp_text: str) -> tuple[list[ScoreCriterion], int]:
        ratings, calls = self.client.ask(prompts.rate_criteria_prompt(icp_text, domain, facts), prompts.RubricRatings)
        criteria = [
            ScoreCriterion(criterion=name, rating=getattr(ratings, name).rating, reasoning=getattr(ratings, name).reasoning)
            for name in RUBRIC_WEIGHTS
        ]
        return criteria, calls

    def draft_email(
        self, domain: str, facts: list[Fact], previous_draft: str, unsupported_claims: list[str], icp_text: str
    ) -> tuple[str, int]:
        prompt = prompts.draft_email_prompt(icp_text, domain, facts, previous_draft, unsupported_claims)
        answer, calls = self.client.ask(prompt, prompts.DraftEmail)
        return answer.text, calls

    def extract_claims(self, domain: str, draft: str, facts: list[Fact]) -> tuple[list[prompts.Claim], int]:
        answer, calls = self.client.ask(prompts.extract_claims_prompt(domain, draft, facts), prompts.DraftClaims)
        return answer.claims, calls
