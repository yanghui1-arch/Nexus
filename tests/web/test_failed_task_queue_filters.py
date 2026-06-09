from pathlib import Path


def test_failed_task_queue_filter_utility_contract() -> None:
    source = Path('web/src/pages/task-board/failedTaskQueue.ts').read_text()

    assert "status === 'failed'" in source
    assert "task.repo === filters.repo" in source
    assert "task.agentLabel === filters.agent" in source
    assert "task.agent === filters.agent" in source
    assert "task.error ?? ''" in source
    assert "toLowerCase().includes(normalizedKeyword)" in source
    assert "finishedAt ?? task.updatedAt" in source
    assert "filters.sortOrder === 'newest'" in source
    assert "localeCompare" in source
