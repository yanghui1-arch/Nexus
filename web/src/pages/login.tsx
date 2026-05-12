import { Github, ShieldCheck, Sparkles, WandSparkles } from 'lucide-react';
import { Button } from '@/components/ui/button';

const LOGIN_HIGHLIGHTS = ['OAuth-first identity', 'One wallet for every agent', 'Instant workspace access'];

export default function LoginPage() {
  return (
    <main className="relative grid min-h-screen overflow-hidden bg-[linear-gradient(135deg,hsl(var(--background)),hsl(var(--muted)))] lg:grid-cols-[1.08fr_0.92fr]">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_12%_12%,hsl(var(--primary)/0.16),transparent_28%),radial-gradient(circle_at_88%_20%,hsl(var(--chart-2)/0.14),transparent_26%)]" />
      <section className="relative hidden overflow-hidden bg-primary text-primary-foreground lg:flex">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_30%_20%,rgba(255,255,255,0.30),transparent_35%),radial-gradient(circle_at_80%_70%,rgba(255,255,255,0.18),transparent_30%)]" />
        <div className="absolute -right-24 top-24 size-72 rounded-full border border-white/20 bg-white/10 blur-sm" />
        <div className="relative z-10 flex flex-col justify-between p-12 xl:p-16">
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
            <div className="grid gap-3 pt-4 sm:grid-cols-3">
              {LOGIN_HIGHLIGHTS.map(highlight => (
                <div key={highlight} className="rounded-2xl border border-white/15 bg-white/10 p-4 text-sm text-primary-foreground/85 shadow-2xl shadow-black/10 backdrop-blur">
                  {highlight}
                </div>
              ))}
            </div>
          </div>
          <div className="flex items-center gap-2 text-sm text-primary-foreground/75">
            <ShieldCheck className="size-4" /> OAuth session cookies are HttpOnly and server verified.
          </div>
        </div>
      </section>

      <section className="relative flex items-center justify-center px-6 py-12">
        <div className="w-full max-w-md rounded-[2rem] border bg-card/85 p-8 shadow-2xl shadow-primary/10 backdrop-blur sm:p-10">
          <div className="space-y-4 text-center">
            <div className="mx-auto flex size-14 items-center justify-center rounded-2xl bg-primary text-primary-foreground shadow-lg shadow-primary/25 lg:hidden">
              <Sparkles className="size-6" />
            </div>
            <div className="mx-auto hidden size-14 items-center justify-center rounded-2xl bg-primary/10 text-primary lg:flex">
              <WandSparkles className="size-6" />
            </div>
            <h2 className="text-3xl font-semibold tracking-tight">Welcome back</h2>
            <p className="text-muted-foreground">Use GitHub to register or sign in to Nexus.</p>
          </div>

          <Button asChild size="lg" className="mt-8 h-12 w-full rounded-xl text-base shadow-lg shadow-primary/20">
            <a href="/v1/auth/github/login">
              <Github className="size-5" /> Continue with GitHub
            </a>
          </Button>

          <p className="mt-6 text-center text-sm leading-6 text-muted-foreground">
            GitHub OAuth App callback should be set to{' '}
            <code>/v1/auth/github/callback</code> on your API host.
          </p>
        </div>
      </section>
    </main>
  );
}
