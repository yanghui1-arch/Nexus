import { useTranslation } from 'react-i18next';
import { Navigate, useLocation } from 'react-router-dom';
import { SiGithub } from 'react-icons/si';
import { useAuth } from '@/components/AuthProvider';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
type LoginLocationState = {
  from?: {
    pathname?: string;
    search?: string;
  };
};

export default function LoginPage() {
  const { t } = useTranslation();
  const location = useLocation();
  const { status } = useAuth();
  const from = (location.state as LoginLocationState | null)?.from;
  const redirectPath = `${from?.pathname ?? '/'}${from?.search ?? ''}`;

  if (status === 'authenticated') {
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
            <Button asChild className="w-full" size="lg">
              <a href="/v1/auth/github/login">
                <SiGithub className="size-5" aria-hidden="true" /> {t('login.continueWithGithub')}
              </a>
            </Button>
          </CardContent>
        </Card>
      </div>
    </main>
  );
}
