import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import LanguageDetector from 'i18next-browser-languagedetector';
import dayjs from 'dayjs';
import 'dayjs/locale/en';
import 'dayjs/locale/zh-cn';
import en from './locales/en/translation.json';
import zh from './locales/zh/translation.json';

// 中英双语初始化。资源内联打包，同步可用，无需 Suspense / I18nextProvider。
// 默认英文（fallbackLng）；只读 localStorage 持久化用户选择，不读 navigator，
// 保证"英文为默认"不被中文 OS 劫持；changeLanguage 后 detector 写回 localStorage。
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

// 同步 dayjs 全局 locale 到 i18n 当前语言，使 `ddd / dddd / MMM / MMMM`
// 等与语言相关的格式串随 UI 语言切换。未识别语言回退到 en。
const syncDayjsLocale = (lang) => {
  const map = { en: 'en', zh: 'zh-cn' };
  dayjs.locale(map[lang] || 'en');
};
syncDayjsLocale(i18n.language || 'en');
i18n.on('languageChanged', syncDayjsLocale);

export default i18n;
