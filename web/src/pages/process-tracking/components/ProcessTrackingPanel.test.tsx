import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ProcessTrackingPanel } from './ProcessTrackingPanel';
import { agents, task } from '../test/fixtures';

function renderPanel(overrides: Partial<Parameters<typeof ProcessTrackingPanel>[0]> = {}) {
  return render(
    <ProcessTrackingPanel
      agents={agents}
      tasksForAgent={[task()]}
      messages={[]}
      timelineEvents={[]}
      isLoadingTimeline={false}
      selectedAgentId="agent-1"
      selectedTaskId="task-1"
      selectedTask={task()}
      input=""
      isLoadingAgents={false}
      isSending={false}
      onSelectedAgentChange={vi.fn()}
      onSelectedTaskChange={vi.fn()}
      onInputChange={vi.fn()}
      onSubmit={vi.fn()}
      {...overrides}
    />,
  );
}

describe('ProcessTrackingPanel', () => {
  it('renders loading state', () => {
    renderPanel({ agents: [], tasksForAgent: [], selectedAgentId: '', selectedTaskId: '', selectedTask: undefined, isLoadingAgents: true });

    expect(screen.getByRole('option', { name: 'Loading agent instances...' })).toBeInTheDocument();
    expect(screen.getByText('No running task selected')).toBeInTheDocument();
  });

  it('renders empty metrics and timeline state', () => {
    renderPanel({ tasksForAgent: [], selectedTaskId: '', selectedTask: undefined });

    expect(screen.getByText('No running tasks available for the selected agent.')).toBeInTheDocument();
    expect(screen.getByText('No key execution events to show yet.')).toBeInTheDocument();
    expect(screen.getByText('Token unknown')).toBeInTheDocument();
  });

  it('renders selected task data, metrics, and timeline', () => {
    vi.setSystemTime(new Date('2026-01-01T09:30:00.000Z'));
    renderPanel();

    expect(screen.getAllByText('Implement observability UI tests').length).toBeGreaterThan(0);
    expect(screen.getByLabelText('Process metrics')).toHaveTextContent('12,345');
    expect(screen.getByLabelText('Process metrics')).toHaveTextContent('gpt-5');
    expect(screen.getByText('Execution timeline')).toBeInTheDocument();
  });

  it('renders failed task errors and Token unknown fallback', () => {
    renderPanel({ selectedTask: task({ status: 'failed', error: 'Agent process exited unexpectedly', modelName: null, tokenCount: null }) });

    expect(screen.getByText('Agent process exited unexpectedly')).toBeInTheDocument();
    expect(screen.getAllByText('Failed')).toHaveLength(1);
    expect(screen.getByText('Token unknown')).toBeInTheDocument();
  });
});
