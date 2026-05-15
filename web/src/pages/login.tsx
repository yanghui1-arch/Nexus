import { SiGithub } from 'react-icons/si';
import { Sparkles } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

export default function LoginPage() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-muted p-6 md:p-10">
      <div className="w-full max-w-sm">
        <Card className="overflow-hidden border-0 shadow-xl">
          <CardHeader className="space-y-4 text-center">
            <div className="mx-auto flex size-12 items-center justify-center rounded-xl bg-primary text-primary-foreground">
              <Sparkles className="size-5" />
            </div>
            <div>
              <CardTitle className="text-2xl">Login to Nexus</CardTitle>
              <CardDescription>Use your GitHub account to continue.</CardDescription>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <Button asChild className="w-full" size="lg">
              <a href="/v1/auth/github/login">
                <SiGithub className="size-5" /> Continue with GitHub
              </a>
            </Button>
            <p className="text-center text-xs text-muted-foreground">
              By continuing, Nexus will create or update your account from GitHub OAuth.
            </p>
          </CardContent>
        </Card>
      </div>
    </main>
  );
}
