from types import SimpleNamespace

import pytest

from src.server.services import task_title


@pytest.mark.asyncio
async def test_generate_task_title_uses_gpt_5_4_mini(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeCompletions:
        async def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content="修复任务看板溢出"))]
            )

    class FakeClient:
        def __init__(self, **kwargs) -> None:
            captured["client"] = kwargs
            self.chat = SimpleNamespace(completions=FakeCompletions())

        async def close(self) -> None:
            return None

    monkeypatch.setattr(task_title, "AsyncOpenAI", FakeClient)

    title = await task_title.generate_task_title(
        "修复活动条目过长时撑宽整个任务看板的问题",
        api_key="test-key",
        base_url="https://api.openai.com/v1",
    )

    assert title == "修复任务看板溢出"
    assert captured["model"] == "gpt-5.4-mini"
    assert captured["reasoning_effort"] == "none"
    messages = captured["messages"]
    assert len(messages) == 2
    assert "Output: 实现任务断点恢复" in messages[0]["content"]
    assert messages[-1]["content"] == "修复活动条目过长时撑宽整个任务看板的问题"
