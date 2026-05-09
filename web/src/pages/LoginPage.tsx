import { useEffect, useState } from 'react';
import { Github, Loader2, Sparkles } from 'lucide-react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { completeGitHubLogin, getGitHubLoginUrl } from '@/api/auth';
import { getErrorDetail } from '@/api/client';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

const STATE_KEY = 'nexus_oauth_state';

function createState() {
  const bytes = crypto.getRandomValues(new Uint32Array(4));
  return Array.from(bytes, value => value.toString(16)).join('');
}

export default function LoginPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const code = params.get('code');
    if (!code) return;

    const state = params.get('state');
    if (state && state !== sessionStorage.getItem(STATE_KEY)) {
      setError('GitHub authorization state mismatch. Please try again.');
      return;
    }

    setLoading(true);
    completeGitHubLogin(code)
      .then(() => navigate('/pricing', { replace: true }))
      .catch(err => setError(getErrorDetail(err, 'GitHub login failed.')))
      .finally(() => setLoading(false));
  }, [navigate, params]);

  async function startGitHubLogin() {
    setError(null);
    setLoading(true);
    const state = createState();
    sessionStorage.setItem(STATE_KEY, state);

    try {
      const { authorization_url } = await getGitHubLoginUrl(state, window.location.href.split('?')[0]);
      window.location.href = authorization_url;
    } catch (err) {
      setError(getErrorDetail(err, 'Unable to start GitHub login.'));
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-[radial-gradient(circle_at_top,hsl(var(--primary)/0.16),transparent_32rem)] px-4 py-10">
      <Card className="w-full max-w-md border-border/70 shadow-2xl">
        <CardHeader className="items-center text-center">
          <div className="mb-2 flex size-12 items-center justify-center rounded-2xl bg-primary text-primary-foreground shadow-sm">
            <Sparkles className="size-5" />
          </div>
          <CardTitle className="text-2xl">Login to Nexus</CardTitle>
          <CardDescription>Continue with GitHub. New users are created automatically after authorization.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {error ? <p className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">{error}</p> : null}
          <Button className="w-full" size="lg" onClick={startGitHubLogin} disabled={loading}>
            {loading ? <Loader2 className="size-4 animate-spin" /> : <Github className="size-4" />}
            Continue with GitHub
          </Button>
          <p className="text-center text-xs text-muted-foreground">
            Configure the GitHub OAuth callback URL as this page URL, for example https://your-web-domain/login.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
