from leadgen.config import RUBRIC_WEIGHTS
from leadgen.llm.prompts import RUBRIC, RubricRatings


def test_rubric_schema_matches_weights():
    # Итог считается по RUBRIC_WEIGHTS: критерий без веса или без поля в схеме сломает score.
    assert list(RubricRatings.model_fields) == list(RUBRIC_WEIGHTS) == list(RUBRIC)
