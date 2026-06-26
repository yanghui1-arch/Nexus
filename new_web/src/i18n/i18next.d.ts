import 'i18next';
import type { resources, defaultLanguage } from './resources';

declare module 'i18next' {
  interface CustomTypeOptions {
    defaultNS: 'translation';
    resources: (typeof resources)[typeof defaultLanguage];
  }
}
