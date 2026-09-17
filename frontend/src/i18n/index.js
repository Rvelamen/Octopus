import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import LanguageDetector from 'i18next-browser-languagedetector';
import en from './locales/en/translation.json';
import zh from './locales/zh/translation.json';

// 中英双语初始化。资源内联打包，同步可用，无需 Suspense / I18nextProvider。
// 默认英文（fallbackLng）；只读 localStorage 持久化用户选择，不读 navigator，
// 保证“英文为默认”不被中文 OS 劫持；changeLanguage 后 detector 写回 localStorage。
i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: {
      en: { translation: en },
      zh: { translation: zh },
    },
    fallbackLng: 'en',
    detection: {
      order: ['localStorage'],
      caches: ['localStorage'],
    },
    interpolation: {
      escapeValue: false, // React 已做 XSS 转义
    },
    returnEmptyString: false,
  });

export default i18n;
