import csv
from pathlib import Path

from leadgen.models import Lead

COLUMNS = [
    "domain",
    "name",
    "description",
    "facts",
    "facts_dropped",
    "score_total",
    "score_criteria",
    "email",
    "email_kind",
    "email_confidence",
    "email_source",
    "draft",
    "status",
]


def write_leads(leads: list[Lead], path: Path) -> None:
    # utf-8-sig — чтобы Excel открыл кириллицу без кракозябр.
    with path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=COLUMNS)
        writer.writeheader()
        for lead in leads:
            writer.writerow({
                "domain": lead.domain,
                "name": lead.name,
                "description": lead.description,
                "facts": "\n".join(
                    f"{fact.kind}: {fact.value} | {fact.source_url} | «{fact.quote}»"
                    for fact in lead.facts
                ),
                "facts_dropped": lead.facts_dropped,
                "score_total": lead.score.total if lead.score else "",
                "score_criteria": "\n".join(
                    f"{item.criterion}={item.rating}: {item.reasoning}"
                    for item in lead.score.criteria
                ) if lead.score else "",
                "email": lead.email.address if lead.email else "",
                "email_kind": lead.email.kind if lead.email else "",
                "email_confidence": lead.email.confidence if lead.email else "",
                "email_source": lead.email.source if lead.email else "",
                "draft": lead.draft,
                "status": lead.status,
            })
