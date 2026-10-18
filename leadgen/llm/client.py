import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path
from typing import TypeVar

from langsmith import traceable
from pydantic import BaseModel

from leadgen.config import LLM_MODEL, LLM_TIMEOUT_SECONDS
from leadgen.storage.llm_cache import LlmCache

T = TypeVar("T", bound=BaseModel)

# Так `claude -p` сообщает, что лимит подписки на текущее окно выбран.
SUBSCRIPTION_LIMIT_RE = re.compile(r"hit your limit|usage limit reached", re.IGNORECASE)


# Сбой самого вызова (код возврата, ошибка в ответе CLI) — такой вызов можно повторить.
class ClaudeError(RuntimeError):
    pass


# Вызовов больше нельзя: выбран лимит запуска (--max-llm-calls) или лимит подписки.
# Повтор не поможет, прогон останавливается и продолжается позже через --resume.
class BudgetExhausted(Exception):
    pass


def find_claude() -> str:
    path = Path(shutil.which("claude"))
    # npm на Windows ставит claude.cmd — обёртку над claude.exe. Через .cmd аргументы идут
    # сквозь cmd.exe, а он портит кавычки и кириллицу в JSON-схеме. Поэтому exe напрямую.
    exe = path.parent / "node_modules" / "@anthropic-ai" / "claude-code" / "bin" / "claude.exe"
    return str(exe) if exe.exists() else str(path)


# Модель по подписке Claude Pro: каждый вызов — отдельный процесс `claude -p`.
# Схема ответа уходит флагом --json-schema, ответ проверяет Pydantic.
class ClaudeClient:
    def __init__(self, cache: LlmCache, system_prompt: str, max_calls: int):
        self.cache = cache
        self.system_prompt = system_prompt
        self.claude = find_claude()
        # Счётчики этого запуска процесса. Лимит проверяется здесь, а не по состоянию графа:
        # ветки параллельны и не видят вызовов друг друга, а этот объект у них общий.
        self.max_calls = max_calls
        self.calls = 0
        self.cache_hits = 0
        self._lock = threading.Lock()  # ask вызывается из параллельных веток

    # Возвращает ответ и число настоящих вызовов модели: 0 — ответ из кэша, 1 — был вызов.
    def ask(self, prompt: str, response_model: type[T]) -> tuple[T, int]:
        schema = json.dumps(response_model.model_json_schema(), ensure_ascii=False)
        key = LlmCache.key(f"{self.system_prompt}\n{prompt}", schema)
        cached = self.cache.get(key)
        if cached is not None:
            with self._lock:
                self.cache_hits += 1
            return response_model.model_validate_json(cached), 0

        with self._lock:
            if self.calls >= self.max_calls:
                raise BudgetExhausted(f"выбран лимит вызовов модели на запуск: {self.max_calls}")
            self.calls += 1
        answer = self._call(prompt, schema)
        # Проверка до записи в кэш: ответ не по схеме не должен пережить перезапуск.
        result = response_model.model_validate_json(answer)
        self.cache.put(key, answer)
        return result, 1

    # run_type="llm" — в LangSmith вызов виден как обращение к модели, с промптом и ответом.
    @traceable(run_type="llm", name="claude -p")
    def _call(self, prompt: str, schema: str) -> str:
        args = [
            self.claude, "-p",
            "--model", LLM_MODEL,
            "--output-format", "json",
            "--json-schema", schema,
            # Свой короткий system prompt вместо промпта Claude Code, без инструментов,
            # настроек, MCP и сохранения сессии: меньше токенов — меньше расход лимита.
            "--system-prompt", self.system_prompt,
            "--tools", "",
            "--setting-sources", "",
            "--strict-mcp-config",
            "--no-session-persistence",
        ]
        # С ANTHROPIC_API_KEY CLI пошёл бы через платный API, а не по подписке.
        env = {name: value for name, value in os.environ.items() if name != "ANTHROPIC_API_KEY"}
        completed = subprocess.run(
            args,
            input=prompt,  # через stdin: тексты страниц не влезут в командную строку Windows
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=env,
            cwd=tempfile.gettempdir(),  # вне проекта, чтобы CLI не подхватил CLAUDE.md
            timeout=LLM_TIMEOUT_SECONDS,
        )
        if completed.returncode != 0 and not completed.stdout:
            if SUBSCRIPTION_LIMIT_RE.search(completed.stderr):
                raise BudgetExhausted(f"лимит подписки: {completed.stderr.strip()}")
            raise ClaudeError(f"claude -p завершился с кодом {completed.returncode}: {completed.stderr.strip()}")
        output = json.loads(completed.stdout)
        # Одни настройки CLI дают один объект-итог, другие — список всех событий сессии.
        result = output[-1] if isinstance(output, list) else output
        if result.get("is_error") or result.get("structured_output") is None:
            if SUBSCRIPTION_LIMIT_RE.search(str(result.get("result"))):
                raise BudgetExhausted(f"лимит подписки: {result.get('result')}")
            raise ClaudeError(f"claude -p: {result.get('subtype')}: {result.get('result')}")
        return json.dumps(result["structured_output"], ensure_ascii=False)
