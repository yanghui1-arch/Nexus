import {
  createContext,
  useContext,
  useLayoutEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import { NavLink, Outlet, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  ChevronDown,
  Grid3X3,
  LogOut,
  Plus,
  Search,
  Tag,
  type LucideIcon,
} from 'lucide-react';
import { SiGithub } from 'react-icons/si';
import { WORKSPACE_NAV_ITEMS } from '@/lib/dashboard-nav';
import { cn } from '@/lib/utils';
import { useAuth } from '@/components/AuthProvider';
import { Button } from '@/components/ui/button';
import { LanguageSwitch } from '@/components/LanguageSwitch';

const NAV_ICON_MAP: Record<string, LucideIcon> = {
  grid: Grid3X3,
  cube: Search,
  plus: Plus,
  search: Search,
  tag: Tag,
};

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
  const { t } = useTranslation();
  const IconComponent = NAV_ICON_MAP[item.icon] || Grid3X3;

  return (
    <NavLink
      to={item.to}
      end
      className={({ isActive }) =>
        cn(
          'flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-all duration-200',
          isActive
            ? 'bg-white/10 text-white shadow-sm'
            : 'text-gray-400 hover:bg-white/5 hover:text-gray-200',
        )
      }
    >
      <IconComponent className="size-4 shrink-0" />
      <span>{t(item.labelKey)}</span>
    </NavLink>
  );
}

function SidebarAccount() {
  const { t } = useTranslation();
  const { signOut, status, user } = useAuth();
  const [isMenuOpen, setIsMenuOpen] = useState(false);

  const handleLogout = async () => {
    await signOut();
    window.location.href = '/login';
  };

  return (
    <div className="relative border-t border-white/10 p-3">
      {user ? (
        <>
          {isMenuOpen ? (
            <div className="absolute bottom-full left-3 right-3 mb-2 rounded-xl border border-white/10 bg-[hsl(0,0%,10%)] p-1 text-sm text-gray-200 shadow-xl">
              <button
                type="button"
                className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-red-400 transition-colors hover:bg-white/5"
                onClick={handleLogout}
              >
                <LogOut className="size-4" /> {t('auth.logout')}
              </button>
            </div>
          ) : null}
          <button
            type="button"
            className="flex w-full items-center gap-3 rounded-xl p-2 text-left text-sm transition-colors hover:bg-white/5"
            onClick={() => setIsMenuOpen(open => !open)}
          >
            <div className="flex size-9 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-lime-400 to-lime-500 text-[hsl(0,0%,10%)]">
              <span className="text-sm font-bold">{user.github_login.charAt(0).toUpperCase()}</span>
            </div>
            <div className="grid min-w-0 flex-1 leading-tight">
              <span className="truncate font-medium text-white">{user.github_login}</span>
              <span className="truncate text-xs text-gray-500">Platform Admin</span>
            </div>
            <ChevronDown className="size-4 text-gray-500" />
          </button>
        </>
      ) : (
        <Button asChild variant="ghost" className="h-auto w-full justify-start gap-3 p-2 text-gray-400 hover:bg-white/5 hover:text-gray-200">
          <a href="/login">
            <div className="flex size-9 shrink-0 items-center justify-center rounded-full bg-white/10">
              <SiGithub className="size-4" />
            </div>
            <span className="truncate text-sm font-medium">{status === 'checking' ? t('auth.loadingAccount') : t('auth.loginWithGithub')}</span>
          </a>
        </Button>
      )}
    </div>
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
  const { t } = useTranslation();
  const location = useLocation();
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

  useLayoutEffect(() => {
    window.scrollTo({ top: 0, left: 0 });
  }, [location.pathname]);

  return (
    <div className="min-h-screen bg-[hsl(0,0%,97%)]">
      <div className="grid min-h-screen md:grid-cols-[260px_minmax(0,1fr)]">
        <aside className="bg-[hsl(0,0%,6%)] md:sticky md:top-0 md:h-screen md:self-start md:overflow-hidden">
          <div className="flex h-full flex-col">
            <div className="flex items-center gap-3 px-5 py-5">
              <div className="flex size-10 items-center justify-center rounded-xl">
                <svg width="36" height="36" viewBox="0 0 36 36" fill="none">
                  <path d="M18 4L22 14L32 18L22 22L18 32L14 22L4 18L14 14L18 4Z" fill="hsl(80,85%,55%)" />
                  <path d="M18 10L20 16L26 18L20 20L18 26L16 20L10 18L16 16L18 10Z" fill="hsl(0,0%,6%)" />
                </svg>
              </div>
              <div className="flex flex-col">
                <p className="text-base font-bold text-white tracking-tight">{t('app.name')}</p>
                <p className="text-xs text-gray-500">{t('app.tagline')}</p>
              </div>
            </div>

            <nav className="flex flex-1 flex-col gap-1 overflow-y-auto px-3 py-2">
              {WORKSPACE_NAV_ITEMS.map(item => (
                <SidebarNavEntry key={item.to} item={item} />
              ))}
            </nav>

            <SidebarAccount />
          </div>
        </aside>

        <AppLayoutContext.Provider value={layoutContextValue}>
          <div className="flex min-w-0 flex-col">
            <header className="sticky top-0 z-30 shrink-0 border-b border-gray-200/60 bg-white/80 backdrop-blur-sm">
              <div className="mx-auto flex w-full max-w-[1600px] items-center gap-3 px-6 py-4">
                <div className="flex min-w-0 flex-col">
                  {layout.title ? (
                    <h1 className="truncate text-2xl font-bold tracking-tight text-[hsl(0,0%,8%)]">{layout.title}</h1>
                  ) : null}
                  {layout.description ? (
                    <p className="mt-0.5 text-sm text-gray-500">{layout.description}</p>
                  ) : null}
                </div>

                <div className="ml-auto flex items-center gap-2">
                  <LanguageSwitch />
                  {layout.topActions}
                </div>
              </div>
            </header>

            <main
              className={cn(
                'mx-auto w-full max-w-[1600px] flex-1 px-6 py-6',
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
