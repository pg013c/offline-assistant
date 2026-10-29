"""Contract for the Reranker port; every adapter must pass it."""

import pytest

from assistant.adapters.fakes.reranker import WordOverlapReranker
from assistant.ports.reranker import Reranker

ADAPTERS = [pytest.param(WordOverlapReranker, id="word-overlap")]

PASSAGES = [
    "Member states designate notified bodies.",
    "Providers keep the logs of high-risk systems for at least six months.",
    "Pasta is cooked in salted water.",
]


@pytest.fixture(params=ADAPTERS)
def reranker(request: pytest.FixtureRequest) -> Reranker:
    factory: type[Reranker] = request.param
    return factory()


def test_there_is_one_score_per_passage_in_order(reranker: Reranker) -> None:
    scores = reranker.score("How long do providers keep logs?", PASSAGES)

    assert len(scores) == len(PASSAGES)
    assert all(isinstance(score, float) for score in scores)


def test_the_passage_that_answers_scores_above_unrelated_ones(reranker: Reranker) -> None:
    scores = reranker.score("How long do providers keep logs?", PASSAGES)

    assert scores[1] > scores[0]
    assert scores[1] > scores[2]


def test_the_same_input_gives_the_same_scores(reranker: Reranker) -> None:
    query = "How long do providers keep logs?"

    assert reranker.score(query, PASSAGES) == reranker.score(query, PASSAGES)


def test_no_passages_give_no_scores(reranker: Reranker) -> None:
    assert reranker.score("How long do providers keep logs?", []) == []


def test_the_model_is_named(reranker: Reranker) -> None:
    assert reranker.model_id
