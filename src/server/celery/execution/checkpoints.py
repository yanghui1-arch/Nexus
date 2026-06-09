from __future__ import annotations

from openai.types.chat.chat_completion_message_param import ChatCompletionMessageParam


def checkpoint_has_completed_turn(checkpoint: list[ChatCompletionMessageParam] | None) -> bool:
    """Return whether a checkpoint ends after a completed assistant turn.

    Args:
        checkpoint: Persisted chat messages for the current task, or ``None``.

    Returns:
        ``True`` when the last message is an assistant response without pending
        tool calls.
    """
    if not checkpoint:
        return False

    last_message = checkpoint[-1]
    return (
        last_message.get("role") == "assistant"
        and not last_message.get("tool_calls")
    )


def checkpoint_completed_prompt(
    checkpoint: list[ChatCompletionMessageParam] | None,
    prompt: str,
) -> bool:
    """Return whether the checkpoint already completed a prompt.

    Args:
        checkpoint: Persisted chat messages for the current task, or ``None``.
        prompt: User prompt that should have been completed.

    Returns:
        ``True`` when the checkpoint ends at a completed assistant turn and the
        latest user message matches ``prompt``.
    """
    return checkpoint_has_completed_turn(checkpoint) and last_user_prompt(checkpoint) == prompt


def checkpoint_completion_text(checkpoint: list[ChatCompletionMessageParam] | None) -> str | None:
    """Extract the final assistant text from a completed checkpoint.

    Args:
        checkpoint: Persisted chat messages for the current task, or ``None``.

    Returns:
        The final assistant message content when the checkpoint is complete;
        otherwise ``None``.
    """
    if not checkpoint_has_completed_turn(checkpoint):
        return None
    return checkpoint[-1].get("content")


def last_user_prompt(checkpoint: list[ChatCompletionMessageParam] | None) -> str | None:
    """Return the latest user prompt stored in a checkpoint.

    Args:
        checkpoint: Persisted chat messages for the current task, or ``None``.

    Returns:
        The latest user message content, or ``None`` when no user message is
        present.
    """
    if not checkpoint:
        return None

    for message in reversed(checkpoint):
        if message.get("role") == "user":
            return message.get("content")
    return None
