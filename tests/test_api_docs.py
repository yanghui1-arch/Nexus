from pathlib import Path


def test_money_response_semantics_are_documented() -> None:
    docs = Path("docs/api.md").read_text()

    assert "integer cents" in docs
    assert "¥19.99" in docs
    assert "Purchase history entries" in docs
    assert "floating-point money errors" in docs
