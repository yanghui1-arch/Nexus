import { useTranslation } from 'react-i18next';
import { Languages } from 'lucide-react';
import type { Language } from '@/i18n/resources';

export function LanguageSwitch() {
  const { i18n, t } = useTranslation();
  const currentLang = i18n.language as Language;
  const nextLang: Language = currentLang === 'zh' ? 'en' : 'zh';

  return (
    <button
      type="button"
      className="inline-flex items-center gap-1.5 rounded-lg border bg-card px-3 py-1.5 text-xs font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
      onClick={() => i18n.changeLanguage(nextLang)}
      title={t('language.switchTo', { language: t(`language.${nextLang}`) })}
    >
      <Languages className="size-3.5" />
      {t(`language.${nextLang}`)}
    </button>
  );
}
