import httpx

from leadgen.models import EmailHit


class HunterEmailFinder:
    def __init__(self, api_key: str):
        self.api_key = api_key

    # Без ключа find() в Hunter не ходит.
    @property
    def external(self) -> bool:
        return bool(self.api_key)

    def find(self, domain: str) -> list[EmailHit]:
        if not self.api_key:
            return []
        response = httpx.get(
            "https://api.hunter.io/v2/domain-search",
            params={"domain": domain, "api_key": self.api_key},
            timeout=30,
        )
        response.raise_for_status()
        hits = []
        for item in response.json()["data"]["emails"]:
            verification = item.get("verification") or {}
            sources = item.get("sources") or []
            hits.append(EmailHit(
                address=item["value"],
                kind="role" if item["type"] == "generic" else "personal",
                source=f"hunter.io: {sources[0]['uri']}" if sources else "hunter.io",
                # Hunter угадывает адреса по шаблону; проверенным считаем только статус valid.
                confidence="high" if verification.get("status") == "valid" else "low_confidence",
            ))
        return hits
