---
paths:
  - "leadgen/graph/**/*.py"
  - "leadgen/state.py"
---

# Код графа

- Узел возвращает словарь только с изменёнными ключами, а не всё состояние.
- Параллельные ветки пишут в общий ключ `OuterState` только через reducer
  (`Annotated[..., operator.add]`), иначе `InvalidUpdateError`.
- Подграф компании работает со своим `CompanyState` и в `OuterState` не пишет:
  результат уходит наружу через `process_company` в `leads`.
- Ветвление — через `add_conditional_edges` и маршрутизаторы, которые читают `status`,
  а не через `if` внутри узла.
- Комментарии по-русски только там, где поведение LangGraph неочевидно.
