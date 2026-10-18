import sqlite3
from pathlib import Path

from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.checkpoint.sqlite import SqliteSaver

from leadgen.models import EmailHit, Fact, FactKind, Lead, Score, ScoreCriterion, Status

# Классы, которые чекпоинтер восстанавливает из базы. Остальные LangGraph
# вернёт голыми словарями (сейчас с предупреждением, в следующих версиях молча).
CHECKPOINT_TYPES = [Status, FactKind, Fact, ScoreCriterion, Score, EmailHit, Lead]


# Чекпоинты лежат в том же leadgen.sqlite, что и кэши, в своих таблицах.
# check_same_thread=False: ветки графа сохраняют результат из разных потоков,
# SqliteSaver сам закрывает соединение блокировкой.
def open_checkpointer(db_path: Path) -> SqliteSaver:
    connection = sqlite3.connect(db_path, check_same_thread=False)
    return SqliteSaver(connection, serde=JsonPlusSerializer(allowed_msgpack_modules=CHECKPOINT_TYPES))
