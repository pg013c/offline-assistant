import pytest

from assistant.domain.routing import needs_tools


@pytest.mark.parametrize(
    "question",
    [
        "What does Article 83 of the GDPR set out?",
        "What does article 5(1) say about purpose limitation?",
        "Co stanowi art. 17 RODO?",
        "Jakie obowiązki nakłada Artykuł 26 aktu o AI?",
        "Which systems does Annex III list?",
        "Co obejmuje załącznik III?",
        "Compare breach notification under the GDPR with incident reporting in the AI Act.",
        "What is the difference between a provider and a deployer?",
        "Porównaj obowiązki dostawców i podmiotów stosujących.",
        "Jaka jest różnica między dostawcą a importerem?",
        "How does the GDPR fine regime differ from the AI Act's?",
    ],
)
def test_questions_about_an_article_or_a_comparison_need_tools(question: str) -> None:
    assert needs_tools(question) is True


@pytest.mark.parametrize(
    "question",
    [
        "When must a personal data breach be notified?",
        "Jakie obowiązki mają podmioty stosujące systemy AI wysokiego ryzyka?",
        "What must providers do so that people know they are talking to an AI?",
        "How long should pasta boil?",
        "Is art therapy covered?",
        "What is an article of clothing?",
    ],
)
def test_other_questions_take_the_search_then_answer_path(question: str) -> None:
    assert needs_tools(question) is False
