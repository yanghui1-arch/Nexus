import { useEffect, useState } from 'react';
import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { Loader2 } from 'lucide-react';
import { getCurrentUser } from '@/api/auth';

type AuthStatus = 'checking' | 'authenticated' | 'unauthenticated';

export default function ProtectedRoute() {
  const location = useLocation();
  const [authStatus, setAuthStatus] = useState<AuthStatus>('checking');

  useEffect(() => {
    let isMounted = true;

    void getCurrentUser()
      .then(() => {
        if (isMounted) {
          setAuthStatus('authenticated');
        }
      })
      .catch(() => {
        if (isMounted) {
          setAuthStatus('unauthenticated');
        }
      });

    return () => {
      isMounted = false;
    };
  }, []);

  if (authStatus === 'checking') {
    return (
      <main className="flex min-h-screen items-center justify-center bg-background text-muted-foreground">
        <div className="flex items-center gap-2 text-sm" role="status" aria-live="polite">
          <Loader2 className="size-4 animate-spin" aria-hidden="true" />
          正在验证登录状态…
        </div>
      </main>
    );
  }

  if (authStatus === 'unauthenticated') {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  return <Outlet />;
}
