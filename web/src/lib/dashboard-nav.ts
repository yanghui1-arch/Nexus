export type WorkspaceNavItem = {
  label: string;
  to: string;
  subItems?: WorkspaceNavItem[];
};

export const DEFAULT_WORKSPACE_PATH = '/task-board';

export const WORKSPACE_NAV_ITEMS: WorkspaceNavItem[] = [
  { label: 'Task Board', to: '/task-board' },
  { label: 'Publish Task', to: '/publish-task' },
  { label: 'Process Tracking', to: '/process-tracking' },
  {
    label: 'Code Review',
    to: '/code-review/nexus',
    subItems: [
      { label: 'Nexus Queue', to: '/code-review/nexus' },
    ],
  },
  { label: 'Pricing', to: '/pricing' },
];
