import {
  createContext,
  useContext,
  useLayoutEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import { NavLink, Outlet, useMatch } from 'react-router-dom';
import { Sparkles } from 'lucide-react';
import { WORKSPACE_NAV_ITEMS } from '@/lib/dashboard-nav';
import { cn } from '@/lib/utils';

type AppLayoutState = {
  title?: string;
  description?: string;
  topActions?: ReactNode;
  mainClassName?: string;
};

type AppLayoutContextValue = {
  resetLayout: () => void;
  setLayout: (state: AppLayoutState) => void;
};

const DEFAULT_LAYOUT_STATE: AppLayoutState = {
  title: '',
  description: '',
  topActions: null,
  mainClassName: undefined,
};

const AppLayoutContext = createContext<AppLayoutContextValue | null>(null);

function SidebarNavEntry({ item }: { item: (typeof WORKSPACE_NAV_ITEMS)[number] }) {
  const isParentActive = useMatch({ path: item.to, end: false });

  return (
    <>
      <NavLink
        to={item.to}
        end={!item.subItems}
        className={({ isActive }) =>
          cn(
            'inline-flex items-center rounded-md px-3 py-2 text-sm transition-colors',
            isActive || (item.subItems && isParentActive)
              ? 'bg-primary text-primary-foreground font-medium shadow-sm'
              : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground',
          )
        }
      >
        {item.label}
      </NavLink>
      {item.subItems && isParentActive ? (
        <div className="ml-3 flex flex-col gap-1 border-l pl-3">
          {item.subItems.map(subItem => (
            <NavLink
              key={subItem.to}
              to={subItem.to}
              end={false}
              className={({ isActive }) =>
                cn(
                  'inline-flex items-center rounded-md px-3 py-1.5 text-sm transition-colors',
                  isActive
                    ? 'bg-primary text-primary-foreground font-medium shadow-sm'
                    : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground',
                )
              }
            >
              {subItem.label}
            </NavLink>
          ))}
        </div>
      ) : null}
    </>
  );
}

export function useAppLayout(state: AppLayoutState) {
  const context = useContext(AppLayoutContext);

  if (!context) {
    throw new Error('useAppLayout must be used within AppLayout.');
  }

  const { description, mainClassName, title, topActions } = state;

  useLayoutEffect(() => {
    context.setLayout({
      title,
      description,
      topActions,
      mainClassName,
    });

    return () => {
      context.resetLayout();
    };
  }, [context, description, mainClassName, title, topActions]);
}

export function AppLayout() {
  const [layout, setLayout] = useState<AppLayoutState>(DEFAULT_LAYOUT_STATE);
  const layoutContextValue = useMemo<AppLayoutContextValue>(
    () => ({
      setLayout,
      resetLayout: () => {
        setLayout(DEFAULT_LAYOUT_STATE);
      },
    }),
    [],
  );
  const showHeader = Boolean(layout.title || layout.description || layout.topActions);

  return (
    <div className="min-h-screen bg-[linear-gradient(180deg,hsl(var(--background)),hsl(var(--muted)/0.55))] lg:h-screen lg:overflow-hidden">
      <div className="grid min-h-screen lg:h-screen lg:grid-cols-[280px_minmax(0,1fr)]">
        {/* Sidebar — fixed height, never grows with page content */}
        <aside className="border-r bg-card/75 backdrop-blur-sm lg:overflow-hidden">
          <div className="flex h-full flex-col">
            <div className="flex items-center gap-3 border-b px-5 py-4">
              <div className="flex size-9 items-center justify-center rounded-lg bg-primary text-primary-foreground shadow-sm">
                <Sparkles className="size-4" />
              </div>
              <div className="flex flex-col">
                <p className="text-sm font-semibold">Nexus</p>
                <p className="text-xs text-muted-foreground">SaaS Control Center</p>
              </div>
            </div>

            <nav className="flex flex-1 flex-col gap-1 overflow-y-auto px-3 py-4">
              {WORKSPACE_NAV_ITEMS.map(item => (
                <SidebarNavEntry key={item.to} item={item} />
              ))}
            </nav>
          </div>
        </aside>

        <AppLayoutContext.Provider value={layoutContextValue}>
          <div className="flex min-h-0 min-w-0 flex-col lg:overflow-hidden">
            {showHeader ? (
              <header className="shrink-0 border-b bg-background/80 backdrop-blur-sm">
                <div className="mx-auto flex w-full max-w-[1600px] items-center gap-3 px-6 py-4">
                  <div className="flex min-w-0 flex-col">
                    {layout.title ? (
                      <h1 className="truncate text-lg font-semibold">{layout.title}</h1>
                    ) : null}
                    {layout.description ? (
                      <p className="text-sm text-muted-foreground">{layout.description}</p>
                    ) : null}
                  </div>

                  {layout.topActions ? (
                    <div className="ml-auto flex items-center gap-2">{layout.topActions}</div>
                  ) : null}
                </div>
              </header>
            ) : null}

            <main
              className={cn(
                'mx-auto flex w-full max-w-[1600px] min-h-0 flex-1 flex-col overflow-y-auto px-6 py-6',
                layout.mainClassName,
              )}
            >
              <Outlet />
            </main>
          </div>
        </AppLayoutContext.Provider>
      </div>
    </div>
  );
}
