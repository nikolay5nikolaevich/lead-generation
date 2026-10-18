import subprocess

import httpx
from langgraph.types import RetryPolicy

from leadgen.llm.client import ClaudeError


# 429 и 5xx — сервис просит подождать или перегружен; TransportError — таймаут, обрыв связи.
# Остальные ошибки (401, кончилась квота, баг в коде) повтор не исправит.
def is_network_glitch(exc: Exception) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code == 429 or exc.response.status_code >= 500
    return isinstance(exc, httpx.TransportError)


# LangGraph перезапускает узел целиком: до 3 попыток с растущей паузой.
NETWORK_RETRY = RetryPolicy(retry_on=is_network_glitch)
# BudgetExhausted сюда не входит: прогон останавливается и ждёт --resume.
LLM_RETRY = RetryPolicy(retry_on=(ClaudeError, subprocess.TimeoutExpired))
