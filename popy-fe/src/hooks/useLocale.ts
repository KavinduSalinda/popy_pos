import { useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { APP_CONFIG } from '@/constants/config';
import {
  DEFAULT_LOCALE,
  isLocale,
  LOCALES,
  LOCALE_LABELS,
  type Locale,
} from '@/i18n/languages';

export const useLocale = () => {
  const { i18n } = useTranslation();
  const languageSwitchEnabled = APP_CONFIG.languageSwitchEnabled;
  const locale: Locale =
    languageSwitchEnabled && isLocale(i18n.language)
      ? i18n.language
      : DEFAULT_LOCALE;

  const setLocale = useCallback(
    (next: Locale) => {
      if (!languageSwitchEnabled) return;
      void i18n.changeLanguage(next);
    },
    [i18n, languageSwitchEnabled],
  );

  return {
    locale,
    setLocale,
    locales: LOCALES,
    labels: LOCALE_LABELS,
    languageSwitchEnabled,
  };
};
