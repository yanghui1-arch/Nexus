import { Languages } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Select } from '@/components/ui/select';

const supportedLanguages = [
  { value: 'zh', labelKey: 'language.zh' },
  { value: 'en', labelKey: 'language.en' },
] as const;

export function LanguageSwitch() {
  const { i18n, t } = useTranslation();
  const currentLanguage = i18n.resolvedLanguage === 'en' ? 'en' : 'zh';

  const handleLanguageChange = (event: React.ChangeEvent<HTMLSelectElement>) => {
    void i18n.changeLanguage(event.target.value);
  };

  return (
    <label className="flex items-center gap-2 text-sm text-muted-foreground">
      <Languages className="size-4" aria-hidden="true" />
      <span className="sr-only">{t('language.label')}</span>
      <Select
        aria-label={t('language.label')}
        className="h-8 w-[104px] bg-background/80 pl-3"
        value={currentLanguage}
        onChange={handleLanguageChange}
      >
        {supportedLanguages.map(language => (
          <option key={language.value} value={language.value}>
            {t(language.labelKey)}
          </option>
        ))}
      </Select>
    </label>
  );
}
