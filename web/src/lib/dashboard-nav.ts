export const DEFAULT_WORKSPACE_PATH = '/task-board';

export const WORKSPACE_NAV_ITEMS = [
  {
    label: 'Task Board',
    to: '/task-board',
  },
  {
    label: 'Publish Task',
    to: '/publish-task',
  },
  {
    label: 'Process Tracking',
    to: '/process-tracking',
  },
  {
    label: 'Product Research',
    to: '/product-research',
  },
  {
    label: 'Code Review',
    to: '/code-review',
    subItems: [
      {
        label: 'Nexus',
        to: '/code-review/nexus',
      },
    ],
  },
  {
    label: 'Pricing',
    to: '/pricing',
  },
] as const;
