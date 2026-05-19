import 'i18next';
import { resources, defaultLanguage } from './resources';

declare module 'i18next' {
  interface CustomTypeOptions {
    defaultNS: 'translation';
    resources: (typeof resources)[typeof defaultLanguage]['translation'];
  }
}
