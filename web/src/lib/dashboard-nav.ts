export const DEFAULT_WORKSPACE_PATH = '/task-board';

export const WORKSPACE_NAV_ITEMS = [
  { label: 'Publish Task', to: '/publish-task' },
  { label: 'Process Tracking', to: '/process-tracking' },
  { label: 'Task Board', to: '/task-board' },
  {
    label: 'Code Review',
    to: '/code-review',
    subItems: [{ label: 'Nexus Reviews', to: '/code-review/nexus' }],
  },
  { label: 'Pricing', to: '/pricing' },
];
