import '@testing-library/jest-dom/vitest';
import { afterEach, vi } from 'vitest';

Element.prototype.scrollIntoView = vi.fn();

window.requestAnimationFrame = callback => window.setTimeout(callback, 0);
window.cancelAnimationFrame = id => window.clearTimeout(id);

afterEach(() => {
  vi.useRealTimers();
});

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, values?: Record<string, unknown>) => {
      const labels: Record<string, string> = {
        'common.agent': 'Agent',
        'common.repository': 'Repository',
        'common.project': 'Project',
        'common.task': 'Task',
        'common.updated': 'Updated',
        'processTracking.loadingAgents': 'Loading agent instances...',
        'processTracking.chooseTask': 'Choose a task...',
        'processTracking.selectAgentFirst': 'Select an agent first',
        'processTracking.selectTaskTitle': 'Select a task',
        'processTracking.selectTaskDescription': 'Choose the running task you want to consult about for this agent.',
        'processTracking.runningTasksAvailable': `${values?.count ?? 0} running task available`,
        'processTracking.noRunningTasks': 'No running tasks available for the selected agent.',
        'processTracking.selectedTask': 'Selected task',
        'processTracking.noTaskSelected': 'No running task selected',
        'processTracking.chat': 'Chat',
        'processTracking.chatHintReady': 'Ask for the latest process, blockers, or ETA.',
        'processTracking.chatHintEmpty': 'Select an agent and task to start chatting.',
        'processTracking.you': 'You',
        'processTracking.agentTyping': 'Agent is typing',
        'processTracking.inputPlaceholderReady': 'Ask for the latest process, blockers, or ETA...',
        'processTracking.inputPlaceholderEmpty': 'Select a task first.',
        'processTracking.consultTask': 'Consult selected task',
        'processTracking.consultFailed': 'Failed to consult agent',
        'processTracking.consultFailedDescription': 'Failed to consult the selected task.',
        'status.running': 'Running',
        'status.failed': 'Failed',
      };
      return labels[key] ?? key;
    },
  }),
}));
