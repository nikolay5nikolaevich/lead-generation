from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DB_PATH = PROJECT_ROOT / "leadgen.sqlite"
FIXTURES_DIR = PROJECT_ROOT / "fixtures"
OUTPUT_CSV = PROJECT_ROOT / "out.csv"

DEFAULT_LIMIT = 10
DEFAULT_MAX_LLM_CALLS = 50
# Сколько компаний обрабатывается одновременно. Каждая ветка — свой процесс `claude -p`,
# без ограничения 50 веток выбирали бы лимит подписки одновременно.
MAX_CONCURRENCY = 4
SEARCH_RESULTS_PER_QUERY = 20  # максимум Tavily
MAX_PAGES_PER_SITE = 4
MAX_CHARS_PER_PAGE = 5000

# Модель для `claude -p`: алиас последней Sonnet. Смена модели не сбрасывает кэш LLM.
LLM_MODEL = "sonnet"
LLM_TIMEOUT_SECONDS = 300

SCORE_THRESHOLD = 60
# Без признаков потребности (need 0 — не нужно, 1 — фактов нет) лид не пишем при любом балле:
# отрасль и регион в широком ICP ставят 3 почти любой компании и сами дотягивают до порога.
NEED_MIN_RATING = 2

# Вес критерия в итоговом балле. Сумма весов = 100, оценка по критерию 0–3.
RUBRIC_WEIGHTS = {
    "industry": 30,
    "size": 25,
    "region": 15,
    "need": 30,
}

STOP_DOMAINS = {
    # соцсети
    "linkedin.com",
    "facebook.com",
    "instagram.com",
    "vk.com",
    "ok.ru",
    "t.me",
    "youtube.com",
    "x.com",
    "livejournal.com",
    # каталоги и агрегаторы
    "2gis.ru",
    "zoon.ru",
    "rusprofile.ru",
    "list-org.com",
    "hh.ru",
    "skladoiskatel.ru",
    "orgpage.ru",
    "4geo.ru",
    "rubrikator.org",
    "ds66.ru",
    "mapquest.com",
    # реестры и базы компаний
    "spark-interfax.ru",
    "tbank.ru",
    "rocketreach.co",
    "zoominfo.com",
    "cbinsights.com",
    # медиа и справочники
    "wikipedia.org",
    "rbc.ru",
    "vc.ru",
    "kp.ru",
    "mk.ru",
    "obozrevatel.com",
    "cryptorank.io",
    # маркетплейсы
    "ozon.ru",
    "wildberries.ru",
    "avito.ru",
}
