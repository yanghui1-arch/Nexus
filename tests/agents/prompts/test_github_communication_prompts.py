from src.agents.sophie.system_prompt import SOPHIE_SYSTEM_PROMPT
from src.agents.tela.system_prompt import TELA_SYSTEM_PROMPT


def test_tela_prompt_guides_human_github_replies():
    assert "like a thoughtful enterprise engineer" in TELA_SYSTEM_PROMPT
    assert "brief acknowledgements for straightforward requested changes" in TELA_SYSTEM_PROMPT
    assert "fuller explanations for design trade-offs" in TELA_SYSTEM_PROMPT


def test_sophie_prompt_guides_human_github_replies():
    assert "like a warm and practical enterprise engineer" in SOPHIE_SYSTEM_PROMPT
    assert "keep simple change acknowledgements short" in SOPHIE_SYSTEM_PROMPT
    assert "explain trade-offs, rationale, style choices" in SOPHIE_SYSTEM_PROMPT
