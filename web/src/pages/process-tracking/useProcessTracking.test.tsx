import { renderHook, waitFor } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { useProcessTracking } from './hooks/useProcessTracking';
import { agents, task } from './test/fixtures';

describe('useProcessTracking', () => {
  it('selects a valid agent and newest running task', async () => {
    const newestRunning = task({ id: 'new', createdAt: '2026-01-01T10:00:00.000Z' });
    const oldRunning = task({ id: 'old', createdAt: '2026-01-01T08:00:00.000Z' });
    const failed = task({ id: 'failed', status: 'failed', createdAt: '2026-01-01T11:00:00.000Z' });

    const { result } = renderHook(() => useProcessTracking({
      agentOptions: agents,
      taskViews: [oldRunning, failed, newestRunning],
    }));

    await waitFor(() => expect(result.current.selectedAgentId).toBe('agent-1'));
    await waitFor(() => expect(result.current.selectedTaskId).toBe('new'));
    expect(result.current.tasksForSelectedAgent.map(item => item.id)).toEqual(['new', 'old']);
    expect(result.current.selectedTrackingTask?.id).toBe('new');
  });

  it('clears selection when no running task remains', async () => {
    const { result, rerender } = renderHook(
      ({ taskViews }) => useProcessTracking({ agentOptions: agents, taskViews }),
      { initialProps: { taskViews: [task()] } },
    );

    await waitFor(() => expect(result.current.selectedTaskId).toBe('task-1'));
    rerender({ taskViews: [task({ status: 'failed' })] });

    await waitFor(() => expect(result.current.selectedTaskId).toBe(''));
    expect(result.current.tasksForSelectedAgent).toEqual([]);
  });
});
