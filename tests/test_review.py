from langgraph.types import Command

from leadgen.graph import outer
from leadgen.storage.checkpoint import open_checkpointer


# Пауза на ревью доменов лежит в чекпоинте: второй граф с новым соединением к тому же файлу
# (как новый процесс) продолжает прогон со списком, который вернул человек.
def test_review_pause_survives_new_checkpointer(tmp_path, monkeypatch):
    monkeypatch.setattr(outer, "OUTPUT_CSV", tmp_path / "out.csv")
    db = tmp_path / "leadgen.sqlite"
    config = {"configurable": {"thread_id": "review"}}

    paused = outer.build_graph(open_checkpointer(db)).invoke(
        {"icp_text": "", "limit": 3, "review_domains": True}, config
    )
    domains = paused["__interrupt__"][0].value
    assert domains == ["severtrans-logistic.ru", "vektor-cargo.ru", "pekarnya-kolosok.ru"]

    final = outer.build_graph(open_checkpointer(db)).invoke(Command(resume=["severtrans-logistic.ru"]), config)
    assert [lead.domain for lead in final["leads"]] == ["severtrans-logistic.ru"]
