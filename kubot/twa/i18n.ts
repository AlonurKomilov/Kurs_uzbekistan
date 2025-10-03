import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import LanguageDetector from 'i18next-browser-languagedetector';

// Import translations
import en from './i18n/en.json';
import ru from './i18n/ru.json';
import uz_cy from './i18n/uz_cy.json';

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: {
      en: { translation: en },
      ru: { translation: ru },
      uz_cy: { translation: uz_cy },
    },
    lng: 'en', // default language
    fallbackLng: 'en',
    debug: process.env.NODE_ENV === 'development',
    
    interpolation: {
      escapeValue: false,
    },
    
    detection: {
      order: ['queryString', 'navigator', 'localStorage'],
      caches: ['localStorage'],
    },
  });

export default i18n;