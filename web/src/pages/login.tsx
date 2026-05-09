import { Github, ShieldCheck, Sparkles } from 'lucide-react';
import { Button } from '@/components/ui/button';

export default function LoginPage() {
  return (
    <main className="grid min-h-screen bg-background lg:grid-cols-2">
      <section className="relative hidden overflow-hidden bg-primary text-primary-foreground lg:flex">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_30%_20%,rgba(255,255,255,0.28),transparent_35%),radial-gradient(circle_at_80%_70%,rgba(255,255,255,0.18),transparent_30%)]" />
        <div className="relative z-10 flex flex-col justify-between p-12">
          <div className="flex items-center gap-3 text-lg font-semibold">
            <span className="flex size-10 items-center justify-center rounded-xl bg-white/15">
              <Sparkles className="size-5" />
            </span>
            Nexus
          </div>
          <div className="max-w-xl space-y-5">
            <p className="text-sm uppercase tracking-[0.3em] text-primary-foreground/70">
              Agent workspace
            </p>
            <h1 className="text-5xl font-semibold tracking-tight">
              Hire Tela and Sophie with one GitHub identity.
            </h1>
            <p className="text-lg text-primary-foreground/80">
              Login authorizes GitHub only. If your account is new, Nexus creates it automatically.
            </p>
          </div>
          <div className="flex items-center gap-2 text-sm text-primary-foreground/75">
            <ShieldCheck className="size-4" /> OAuth session cookies are HttpOnly and server verified.
          </div>
        </div>
      </section>

      <section className="flex items-center justify-center px-6 py-12">
        <div className="w-full max-w-md space-y-8">
          <div className="space-y-3 text-center">
            <div className="mx-auto flex size-12 items-center justify-center rounded-2xl bg-primary text-primary-foreground shadow-sm lg:hidden">
              <Sparkles className="size-5" />
            </div>
            <h2 className="text-3xl font-semibold tracking-tight">Welcome back</h2>
            <p className="text-muted-foreground">Use GitHub to register or sign in to Nexus.</p>
          </div>

          <Button asChild size="lg" className="h-12 w-full text-base">
            <a href="/v1/auth/github/login">
              <Github className="size-5" /> Continue with GitHub
            </a>
          </Button>

          <p className="text-center text-sm text-muted-foreground">
            GitHub OAuth App callback should be set to{' '}
            <code>/v1/auth/github/callback</code> on your API host.
          </p>
        </div>
      </section>
    </main>
  );
}
