import { NavLink, Outlet, useMatch } from 'react-router-dom';
import { Sparkles } from 'lucide-react';
import {
  OVERVIEW_NAV_ITEMS,
  WORKSPACE_NAV_ITEMS,
} from '@/lib/dashboard-nav';
import { cn } from '@/lib/utils';

function WorkspaceNavEntry({ item }: { item: (typeof WORKSPACE_NAV_ITEMS)[number] }) {
  const isParentActive = useMatch({ path: item.to, end: false });

  return (
    <>
      <NavLink
        to={item.to}
        end={!item.subItems}
        className={({ isActive }) =>
          cn(
            'inline-flex items-center rounded-md px-3 py-1.5 text-sm transition-colors',
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
          {item.subItems.map(sub => (
            <NavLink
              key={sub.to}
              to={sub.to}
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
              {sub.label}
            </NavLink>
          ))}
        </div>
      ) : null}
    </>
  );
}

export function AppLayout() {
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

            <nav className="flex flex-1 flex-col gap-6 overflow-y-auto px-3 py-4">
              <section className="flex flex-col gap-2">
                <p className="px-3 text-sm font-semibold tracking-tight text-foreground/80">
                  Workspace
                </p>
                <div className="ml-3 flex flex-col gap-1 border-l pl-3">
                  {WORKSPACE_NAV_ITEMS.map(item => (
                    <WorkspaceNavEntry key={item.to} item={item} />
                  ))}
                </div>
              </section>

              <section className="flex flex-col gap-2">
                <p className="px-3 text-sm font-semibold tracking-tight text-foreground/80">
                  Overview
                </p>
                <div className="ml-3 flex flex-col gap-1 border-l pl-3">
                  {OVERVIEW_NAV_ITEMS.map(item => (
                    <NavLink
                      key={item.to}
                      to={item.to}
                      end
                      className={({ isActive }) =>
                        cn(
                          'inline-flex items-center rounded-md px-3 py-1.5 text-sm transition-colors',
                          isActive
                            ? 'bg-primary text-primary-foreground font-medium shadow-sm'
                            : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground',
                        )
                      }
                    >
                      {item.label}
                    </NavLink>
                  ))}
                </div>
              </section>
            </nav>
          </div>
        </aside>

        {/* Right column — each page controls its own scroll behavior */}
        <div className="flex min-h-0 min-w-0 flex-col lg:overflow-hidden">
          <Outlet />
        </div>
      </div>
    </div>
  );
}
