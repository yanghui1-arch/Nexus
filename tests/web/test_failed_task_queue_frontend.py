from pathlib import Path

FAILED_TASK_QUEUE = Path("web/src/pages/task-board/failedTaskQueue.ts")
USE_WORKSPACE_RECORDS = Path("web/src/lib/useWorkspaceRecords.ts")


def test_failed_task_queue_uses_default_failed_task_request_params():
    source = USE_WORKSPACE_RECORDS.read_text()

    assert "listTasks({ limit: 200 })" in source


def test_failed_task_queue_filter_utility_contract():
    source = FAILED_TASK_QUEUE.read_text()

    assert "DEFAULT_FAILED_TASK_QUEUE_FILTERS" in source
    assert "status === 'failed'" in source
    assert "task.repo === filters.repo" in source
    assert "task.agentLabel === filters.agent" in source
    assert "task.agent === filters.agent" in source
    assert "task.error ?? ''" in source
    assert "toLowerCase()" in source
    assert ".includes(normalizedKeyword)" in source
    assert "finishedAt ?? task.updatedAt" in source
    assert "filters.sortOrder === 'newest'" in source
    assert "localeCompare" in source


def test_failed_task_queue_helpers_cover_rendering_empty_and_error_contracts():
    source = FAILED_TASK_QUEUE.read_text()

    assert "getFailedTaskQueueTasks" in source
    assert "deriveFailedTaskQueueRepoOptions" in source
    assert "deriveFailedTaskQueueAgentOptions" in source
    assert "FAILED_TASK_QUEUE_ALL_REPOSITORIES" in source
    assert "FAILED_TASK_QUEUE_ALL_AGENTS" in source
