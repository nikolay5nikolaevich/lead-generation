from leadgen.graph.log import log
from leadgen.models import Status
from leadgen.providers.fake import FakePageFetcher
from leadgen.state import CompanyState

page_fetcher = FakePageFetcher()


def fetch_pages(state: CompanyState) -> dict:
    pages = page_fetcher.fetch(state["domain"])
    log(state["domain"], f"fetch_pages, страниц {len(pages)}")
    if not pages:
        return {"pages": {}, "status": Status.NO_DATA}
    return {"pages": pages}
