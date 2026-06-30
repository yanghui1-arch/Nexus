from openai import AsyncOpenAI

TASK_TITLE_MODEL = "gpt-5.4-mini"
TASK_TITLE_MAX_LENGTH = 80

TITLE_INSTRUCTIONS = """Write a short title for the task in the same language as the request.
Describe only the main action and object. Keep Chinese titles within 20 characters and English
titles within 8 words. Remove template prefixes and implementation details. Return only the title.

Examples:
Input: Implement product feature item: 实现 Retry from Checkpoint API，允许失败任务从 checkpoint 恢复执行。
Output: 实现任务断点恢复

Input: Implement product feature item: 增加失败任务恢复入口并扩展 Process Tracking/Task Board。
Output: 增加失败任务恢复入口

Input: Fix the task board layout when a long activity item expands the entire application width.
Output: Fix task board overflow"""


async def generate_task_title(
    question: str,
    *,
    api_key: str,
    base_url: str,
) -> str:
    """Generate the compact display title stored with a task."""
    client = AsyncOpenAI(api_key=api_key, base_url=base_url)
    try:
        completion = await client.chat.completions.create(
            model=TASK_TITLE_MODEL,
            reasoning_effort="none",
            max_completion_tokens=64,
            messages=[
                {"role": "system", "content": TITLE_INSTRUCTIONS},
                {"role": "user", "content": question},
            ],
        )
        title = (completion.choices[0].message.content or "").strip()
        if not title:
            raise ValueError("Task title generation returned an empty response")
        return title[:TASK_TITLE_MAX_LENGTH]
    finally:
        await client.close()
