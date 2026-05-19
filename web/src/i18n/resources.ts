import resourcesJson from './resources.json';

export const resources = resourcesJson;

export type Language = keyof typeof resources;
export const defaultLanguage: Language = 'zh';
