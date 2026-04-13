import { type ReactNode } from 'react';
import { NavLink } from 'react-router-dom';
import { Sparkles } from 'lucide-react';
import {
  OVERVIEW_NAV_ITEMS,
  WORKSPACE_NAV_ITEMS,
} from '@/lib/dashboard-nav';
import { cn } from '@/lib/utils';

type DashboardShellProps = {
  title: string;
  description: string;
  topActions?: ReactNode;
  sideContent?: ReactNode;
  children: ReactNode;
};

export function DashboardShell({
  title,
  description,
  topActions,
  sideContent,
  children,
}: DashboardShellProps) {
  return (
    <div className="min-h-screen bg-[linear-gradient(180deg,hsl(var(--background)),hsl(var(--muted)/0.55))]">
      <div className="grid min-h-screen lg:h-screen lg:grid-cols-[280px_minmax(0,1fr)]">
        <aside className="border-r bg-card/75 backdrop-blur-sm lg:min-h-0">
          <div className="flex h-full min-h-0 flex-col">
            <div className="flex items-center gap-3 border-b px-5 py-4">
              <div className="flex size-9 items-center justify-center rounded-lg bg-primary text-primary-foreground shadow-sm">
                <Sparkles className="size-4" />
              </div>
              <div className="flex flex-col">
                <p className="text-sm font-semibold">Nexus</p>
                <p className="text-xs text-muted-foreground">SaaS Control Center</p>
              </div>
            </div>

            <div className="flex min-h-0 flex-1 flex-col">
              <nav className="flex min-h-0 flex-1 flex-col gap-6 overflow-y-auto px-3 py-4">
                <section className="flex flex-col gap-2">
                  <p className="px-3 text-sm font-semibold tracking-tight text-foreground/80">
                    Workspace
                  </p>
                  <div className="ml-3 flex flex-col gap-1 border-l pl-3">
                    {WORKSPACE_NAV_ITEMS.map(item => (
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

              {sideContent ? (
                <div className="border-t px-3 py-4 lg:max-h-72 lg:overflow-y-auto">
                  {sideContent}
                </div>
              ) : null}
            </div>
          </div>
        </aside>

        <div className="min-w-0 lg:flex lg:min-h-0 lg:flex-col">
          <header className="border-b bg-background/80 backdrop-blur-sm">
            <div className="mx-auto flex w-full max-w-[1600px] items-center gap-3 px-6 py-4">
              <div className="flex min-w-0 flex-col">
                <h1 className="truncate text-lg font-semibold">{title}</h1>
                <p className="text-sm text-muted-foreground">{description}</p>
              </div>

              {topActions ? (
                <div className="ml-auto flex items-center gap-2">{topActions}</div>
              ) : null}
            </div>
          </header>

          <main className="mx-auto w-full max-w-[1600px] px-6 py-6 lg:flex-1 lg:min-h-0 lg:overflow-y-auto">
            {children}
          </main>
        </div>
      </div>
    </div>
  );
}
