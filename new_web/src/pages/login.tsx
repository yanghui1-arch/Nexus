import { useTranslation } from 'react-i18next';
import { SiGithub } from 'react-icons/si';

export default function LoginPage() {
  const { t } = useTranslation();

  const handleLogin = () => {
    window.location.href = '/v1/auth/login/github';
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-[hsl(0,0%,97%)]">
      <div className="w-full max-w-md rounded-2xl border border-gray-200/60 bg-white p-8 shadow-sm">
        <div className="mb-6 flex justify-center">
          <svg width="48" height="48" viewBox="0 0 36 36" fill="none">
            <path d="M18 4L22 14L32 18L22 22L18 32L14 22L4 18L14 14L18 4Z" fill="hsl(80,85%,55%)" />
            <path d="M18 10L20 16L26 18L20 20L18 26L16 20L10 18L16 16L18 10Z" fill="hsl(0,0%,6%)" />
          </svg>
        </div>
        <h1 className="text-center text-xl font-bold text-[hsl(0,0%,8%)]">{t('login.title')}</h1>
        <p className="mt-2 text-center text-sm text-gray-500">{t('login.description')}</p>
        <button
          type="button"
          onClick={handleLogin}
          className="mt-6 flex w-full items-center justify-center gap-2 rounded-xl bg-[hsl(0,0%,8%)] px-4 py-3 text-sm font-medium text-white transition-colors hover:bg-[hsl(0,0%,20%)]"
        >
          <SiGithub className="size-4" />
          {t('login.continueWithGithub')}
        </button>
      </div>
    </div>
  );
}
