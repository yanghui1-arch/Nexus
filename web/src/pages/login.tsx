import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Navigate, useLocation } from 'react-router-dom';
import { Loader2 } from 'lucide-react';
import { SiGithub } from 'react-icons/si';
import { getCurrentUser } from '@/api/auth';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

type LoginLocationState = {
  from?: {
    pathname?: string;
    search?: string;
  };
};

type AuthStatus = 'checking' | 'authenticated' | 'unauthenticated';

export default function LoginPage() {
  const { t } = useTranslation();
  const location = useLocation();
  const [authStatus, setAuthStatus] = useState<AuthStatus>('checking');
  const from = (location.state as LoginLocationState | null)?.from;
  const redirectPath = `${from?.pathname ?? '/'}${from?.search ?? ''}`;

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

  if (authStatus === 'authenticated') {
    return <Navigate to={redirectPath} replace />;
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-muted p-6 md:p-10">
      <div className="w-full max-w-sm">
        <Card className="overflow-hidden border-0 shadow-xl">
          <CardHeader className="space-y-4 text-center">
            <div>
              <CardTitle className="text-2xl">{t('login.title')}</CardTitle>
              <CardDescription>{t('login.description')}</CardDescription>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <Button asChild className="w-full" disabled={authStatus === 'checking'} size="lg">
              <a href="/v1/auth/github/login" aria-disabled={authStatus === 'checking'}>
                {authStatus === 'checking' ? (
                  <Loader2 className="size-5 animate-spin" aria-hidden="true" />
                ) : (
                  <SiGithub className="size-5" aria-hidden="true" />
                )}
                {authStatus === 'checking' ? t('auth.loadingAccount') : t('login.continueWithGithub')}
              </a>
            </Button>
          </CardContent>
        </Card>
      </div>
    </main>
  );
}
