import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';
import { Loader2, ShieldCheck, Sparkles } from 'lucide-react';
import { exchangeGithubCode, getCurrentUser, getGithubLoginUrl } from '@/api/auth';
import { getErrorDetail } from '@/api/client';
import type { ApiUser } from '@/api/types';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { clearStoredAuthToken, getStoredAuthToken, storeAuthToken } from '@/lib/auth';

const AUTH_REDIRECT_STORAGE_KEY = 'nexus.auth_redirect';

function createOAuthState() {
  const state = crypto.randomUUID();
  sessionStorage.setItem('nexus.github_oauth_state', state);
  return state;
}

function getFriendlyAuthError(error: unknown) {
  const message = getErrorDetail(error, 'Unable to continue with GitHub.');
  if (message.includes('NEXUS_GITHUB_OAUTH_CLIENT_ID')) {
    return 'GitHub OAuth is not configured yet. Please set the OAuth client id on the server.';
  }
  return message;
}

export function LoginPage() {
  const [isCheckingSession, setIsCheckingSession] = useState(Boolean(getStoredAuthToken()));
  const [isStartingGithub, setIsStartingGithub] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const navigate = useNavigate();
  const location = useLocation();

  const redirectTo = useMemo(() => {
    const requestedPath = location.state && typeof location.state === 'object' && 'from' in location.state
      ? (location.state.from as { pathname?: string } | undefined)?.pathname
      : undefined;
    return requestedPath && requestedPath !== '/login' ? requestedPath : '/pricing';
  }, [location.state]);

  useEffect(() => {
    if (!getStoredAuthToken()) return;
    let cancelled = false;
    getCurrentUser()
      .then(() => {
        if (!cancelled) navigate(redirectTo, { replace: true });
      })
      .catch(() => {
        clearStoredAuthToken();
        if (!cancelled) setIsCheckingSession(false);
      });
    return () => {
      cancelled = true;
    };
  }, [navigate, redirectTo]);

  const handleGithubLogin = useCallback(async () => {
    setIsStartingGithub(true);
    setErrorMessage(null);
    try {
      sessionStorage.setItem(AUTH_REDIRECT_STORAGE_KEY, redirectTo);
      const { authorization_url } = await getGithubLoginUrl(createOAuthState());
      window.location.assign(authorization_url);
    } catch (error) {
      setErrorMessage(getFriendlyAuthError(error));
      setIsStartingGithub(false);
    }
  }, [redirectTo]);

  if (isCheckingSession) {
    return (
      <AuthShell>
        <div className="flex items-center gap-3 rounded-full border bg-background/80 px-4 py-2 text-sm text-muted-foreground shadow-sm">
          <Loader2 className="size-4 animate-spin" aria-hidden="true" />
          Checking your session…
        </div>
      </AuthShell>
    );
  }

  return (
    <AuthShell>
      <Card className="w-full max-w-[420px] border-border/80 bg-card/95 shadow-2xl shadow-slate-950/10 backdrop-blur">
        <CardContent className="space-y-8 px-7 py-8 sm:px-9">
          <div className="space-y-3 text-center">
            <div className="mx-auto flex size-12 items-center justify-center rounded-2xl bg-primary text-primary-foreground shadow-lg shadow-primary/20">
              <Sparkles className="size-5" aria-hidden="true" />
            </div>
            <div className="space-y-2">
              <h1 className="text-2xl font-semibold tracking-tight">Welcome back to Nexus</h1>
              <p className="text-sm leading-6 text-muted-foreground">
                Continue with GitHub to manage your agents, subscriptions, and review workflow.
              </p>
            </div>
          </div>

          {errorMessage ? (
            <div role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
              {errorMessage}
            </div>
          ) : null}

          <Button type="button" size="lg" className="h-12 w-full rounded-xl text-base" onClick={handleGithubLogin} disabled={isStartingGithub}>
            {isStartingGithub ? <Loader2 className="size-5 animate-spin" aria-hidden="true" /> : <GithubMark className="size-5" aria-hidden="true" />}
            Continue with GitHub
          </Button>

          <div className="flex items-start gap-3 rounded-xl bg-muted/70 p-4 text-left text-xs leading-5 text-muted-foreground">
            <ShieldCheck className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden="true" />
            <p>We only request GitHub identity access. If this is your first sign-in, Nexus creates your account automatically after authorization.</p>
          </div>
        </CardContent>
      </Card>
    </AuthShell>
  );
}

export function AuthCallbackPage() {
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const location = useLocation();
  const navigate = useNavigate();

  useEffect(() => {
    let cancelled = false;
    const params = new URLSearchParams(location.search);
    const code = params.get('code');
    const error = params.get('error_description') ?? params.get('error');

    if (error) {
      setErrorMessage(error);
      return;
    }
    if (!code) {
      setErrorMessage('GitHub did not return an authorization code. Please try again.');
      return;
    }

    exchangeGithubCode(code)
      .then(({ access_token }) => {
        if (cancelled) return;
        storeAuthToken(access_token);
        const redirectTo = sessionStorage.getItem(AUTH_REDIRECT_STORAGE_KEY) ?? '/pricing';
        sessionStorage.removeItem(AUTH_REDIRECT_STORAGE_KEY);
        navigate(redirectTo, { replace: true });
      })
      .catch(error => {
        if (!cancelled) setErrorMessage(getFriendlyAuthError(error));
      });

    return () => {
      cancelled = true;
    };
  }, [location.search, navigate]);

  return (
    <AuthShell>
      <Card className="w-full max-w-[420px] border-border/80 bg-card/95 shadow-xl">
        <CardContent className="space-y-5 px-8 py-8 text-center">
          {errorMessage ? (
            <>
              <h1 className="text-xl font-semibold">GitHub sign-in failed</h1>
              <p role="alert" className="text-sm leading-6 text-muted-foreground">{errorMessage}</p>
              <Button asChild className="w-full"><a href="/login">Try again</a></Button>
            </>
          ) : (
            <>
              <Loader2 className="mx-auto size-8 animate-spin text-primary" aria-hidden="true" />
              <h1 className="text-xl font-semibold">Finishing GitHub sign-in…</h1>
              <p className="text-sm text-muted-foreground">Creating your Nexus session securely.</p>
            </>
          )}
        </CardContent>
      </Card>
    </AuthShell>
  );
}

export function RequireAuth({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<ApiUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const location = useLocation();

  useEffect(() => {
    if (!getStoredAuthToken()) {
      setIsLoading(false);
      return;
    }
    let cancelled = false;
    getCurrentUser()
      .then(currentUser => {
        if (!cancelled) setUser(currentUser);
      })
      .catch(() => clearStoredAuthToken())
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (isLoading) {
    return <div className="grid min-h-screen place-items-center"><Loader2 className="size-7 animate-spin text-primary" /></div>;
  }
  if (!user) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }
  return children;
}

function AuthShell({ children }: { children: ReactNode }) {
  return (
    <main className="relative grid min-h-screen overflow-hidden bg-[radial-gradient(circle_at_top_left,hsl(var(--primary)/0.16),transparent_32%),linear-gradient(135deg,hsl(var(--background)),hsl(var(--muted)))] px-4 py-10">
      <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-primary/40 to-transparent" />
      <section className="mx-auto grid w-full max-w-6xl items-center gap-10 lg:grid-cols-[1.05fr_0.95fr]">
        <div className="hidden space-y-6 lg:block">
          <p className="text-sm font-medium uppercase tracking-[0.28em] text-primary">Nexus Agent Workspace</p>
          <h2 className="max-w-xl text-5xl font-semibold tracking-tight text-foreground">Human-centered automation for engineering teams.</h2>
          <p className="max-w-lg text-lg leading-8 text-muted-foreground">Sign in once, choose the agent capability you need, and let Sophie or Tela help move implementation and review work forward.</p>
        </div>
        <div className="flex justify-center">{children}</div>
      </section>
    </main>
  );
}

function GithubMark({ className, ...props }: React.ComponentProps<'svg'>) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className={className} {...props}>
      <path d="M12 .5C5.65.5.5 5.65.5 12c0 5.08 3.29 9.39 7.86 10.91.58.11.79-.25.79-.56v-2.02c-3.2.7-3.87-1.37-3.87-1.37-.52-1.33-1.28-1.69-1.28-1.69-1.05-.72.08-.7.08-.7 1.16.08 1.77 1.19 1.77 1.19 1.03 1.76 2.7 1.25 3.36.96.1-.75.4-1.25.73-1.54-2.56-.29-5.25-1.28-5.25-5.69 0-1.26.45-2.29 1.19-3.09-.12-.29-.52-1.46.11-3.05 0 0 .97-.31 3.17 1.18A11 11 0 0 1 12 6.14c.98 0 1.96.13 2.88.39 2.2-1.49 3.17-1.18 3.17-1.18.63 1.59.23 2.76.11 3.05.74.8 1.19 1.83 1.19 3.09 0 4.42-2.7 5.39-5.27 5.67.42.36.79 1.07.79 2.16v3.03c0 .31.21.68.8.56A11.51 11.51 0 0 0 23.5 12C23.5 5.65 18.35.5 12 .5Z" />
    </svg>
  );
}
