import time


# Строка лога на каждый выполненный узел компании: по логу видно, что после --resume
# готовая работа не переделывается. llm_calls — сколько настоящих вызовов модели сделал узел.
def log(domain: str, text: str, llm_calls: int | None = None) -> None:
    if llm_calls is not None:
        text += ", вызов модели" if llm_calls else ", ответ из кэша"
    print(f"{time.strftime('%H:%M:%S')}  {domain}: {text}", flush=True)
