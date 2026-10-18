import httpx


class TavilySearchProvider:
    def __init__(self, api_key: str):
        self.api_key = api_key

    def search(self, query: str, max_results: int) -> list[str]:
        response = httpx.post(
            "https://api.tavily.com/search",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={"query": query, "max_results": max_results},
            timeout=30,
        )
        response.raise_for_status()
        return [result["url"] for result in response.json()["results"]]
