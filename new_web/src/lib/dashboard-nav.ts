export const DEFAULT_WORKSPACE_PATH = '/task-board';

export const WORKSPACE_NAV_ITEMS = [
  {
    labelKey: 'nav.taskBoard',
    to: '/task-board',
    icon: 'grid' as const,
  },
  {
    labelKey: 'nav.workspaces',
    to: '/workspace-settings',
    icon: 'cube' as const,
  },
  {
    labelKey: 'nav.publishTask',
    to: '/publish-task',
    icon: 'plus' as const,
  },
  {
    labelKey: 'nav.productResearch',
    to: '/product-research',
    icon: 'search' as const,
  },
  {
    labelKey: 'nav.pricing',
    to: '/pricing',
    icon: 'tag' as const,
  },
] as const;
