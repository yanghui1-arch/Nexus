export const DEFAULT_WORKSPACE_PATH = '/task-board';

export const WORKSPACE_NAV_ITEMS = [
  {
    labelKey: 'nav.taskBoard',
    to: '/task-board',
  },
  {
    labelKey: 'nav.workspaceSettings',
    to: '/workspace-settings',
  },
  {
    labelKey: 'nav.publishTask',
    to: '/publish-task',
  },
  {
    labelKey: 'nav.processTracking',
    to: '/process-tracking',
  },
  {
    labelKey: 'nav.failedTaskQueue',
    to: '/failed-task-queue',
  },
  {
    labelKey: 'nav.productResearch',
    to: '/product-research',
  },
  {
    labelKey: 'nav.codeReview',
    to: '/code-review',
    subItems: [
      {
        labelKey: 'app.name',
        to: '/code-review/nexus',
      },
    ],
  },
  {
    labelKey: 'nav.pricing',
    to: '/pricing',
  },
] as const;
