from leadgen.graph.nodes.validate import validate_facts
from leadgen.models import Fact

URL = "https://example.ru/about"
PAGE = "Компания «Север» — это 180 сотрудников и   склад класса А.\nРаботаем с 2009 года."


def run(quote: str, url: str = URL) -> dict:
    fact = Fact(kind="size", value="180 сотрудников", source_url=url, quote=quote)
    return validate_facts({"domain": "example.ru", "pages": {URL: PAGE}, "facts": [fact]})


def test_invented_quote_is_dropped():
    result = run("У нас 500 сотрудников и три склада класса А.")
    assert result["facts"] == []
    assert result["facts_dropped"] == 1


def test_quote_from_page_not_fetched_is_dropped():
    result = run("это 180 сотрудников", url="https://example.ru/contacts")
    assert result["facts_dropped"] == 1


def test_whitespace_quotes_and_case_differences_pass():
    result = run('компания "Север" — это 180 сотрудников и склад класса а.')
    assert len(result["facts"]) == 1
    assert result["facts_dropped"] == 0


def test_quote_across_line_break_passes():
    result = run("склад класса А. Работаем с 2009 года")
    assert result["facts_dropped"] == 0
