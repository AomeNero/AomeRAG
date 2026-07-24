from aome_rag.providers.base import LLMProvider

from tests.fakes import FakeProvider


def test_fake_satisfies_protocol() -> None:
    assert isinstance(FakeProvider(), LLMProvider)
