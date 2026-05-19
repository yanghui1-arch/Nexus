import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import { defaultLanguage, resources, type Language } from './resources';

const storageKey = 'nexus-language';

function getInitialLanguage(): Language {
  const storedLanguage = localStorage.getItem(storageKey);
  return storedLanguage === 'en' || storedLanguage === 'zh' ? storedLanguage : defaultLanguage;
}

i18n.use(initReactI18next).init({
  resources,
  lng: getInitialLanguage(),
  fallbackLng: defaultLanguage,
  supportedLngs: ['zh', 'en'],
  interpolation: { escapeValue: false },
});

i18n.on('languageChanged', (language) => {
  if (language === 'zh' || language === 'en') {
    localStorage.setItem(storageKey, language);
    document.documentElement.lang = language === 'zh' ? 'zh-CN' : 'en';
  }
});

document.documentElement.lang = i18n.language === 'en' ? 'en' : 'zh-CN';

export default i18n;
