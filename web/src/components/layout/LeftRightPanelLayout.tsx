import { type ReactNode } from 'react';
import { cn } from '@/lib/utils';

type LeftRightPanelLayoutProps = {
  brand: ReactNode;
  headerActions?: ReactNode;
  sidebar: ReactNode;
  mainHeader: ReactNode;
  children: ReactNode;
  pageBgClassName?: string;
  surfaceClassName?: string;
  sidebarBgClassName?: string;
  borderClassName?: string;
  sidebarWidthClassName?: string;
  rootClassName?: string;
  sidebarClassName?: string;
  mainClassName?: string;
  contentClassName?: string;
};

export function LeftRightPanelLayout({
  brand,
  headerActions,
  sidebar,
  mainHeader,
  children,
  pageBgClassName = 'bg-[#F2EDE4]',
  surfaceClassName = 'bg-[#FDFAF6]',
  sidebarBgClassName = 'bg-[#EAE4DA]',
  borderClassName = 'border-[#DDD7CE]',
  sidebarWidthClassName = 'w-56',
  rootClassName,
  sidebarClassName,
  mainClassName,
  contentClassName,
}: LeftRightPanelLayoutProps) {
  return (
    <div className={cn('flex flex-col h-screen overflow-hidden', pageBgClassName, rootClassName)}>
      <header className={cn('h-12 shrink-0 flex items-center px-5 gap-3 border-b', surfaceClassName, borderClassName)}>
        {brand}
        {headerActions && (
          <div className="ml-auto flex items-center gap-1.5">
            {headerActions}
          </div>
        )}
      </header>

      <div className="flex flex-1 overflow-hidden">
        <aside className={cn('shrink-0 border-r overflow-y-auto', sidebarWidthClassName, sidebarBgClassName, borderClassName, sidebarClassName)}>
          {sidebar}
        </aside>

        <main className={cn('flex-1 overflow-y-auto min-w-0', pageBgClassName, mainClassName)}>
          <div className={cn('border-b px-6 py-4', surfaceClassName, borderClassName)}>
            {mainHeader}
          </div>

          <div className={cn('p-4', contentClassName)}>
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}
