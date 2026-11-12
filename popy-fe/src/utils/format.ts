import dayjs from 'dayjs';
import { APP_CONFIG } from '@/constants';

/** Coerce API decimals (often JSON strings) into a finite number. */
export const toNumber = (value: unknown): number => {
  if (typeof value === 'number') {
    return Number.isFinite(value) ? value : 0;
  }
  if (typeof value === 'string' && value.trim() !== '') {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : 0;
  }
  return 0;
};

export const formatCurrency = (value: unknown): string => {
  const amount = toNumber(value);
  return new Intl.NumberFormat(APP_CONFIG.locale, {
    style: 'currency',
    currency: APP_CONFIG.currency,
  }).format(amount);
};

export const formatNumber = (value: unknown): string =>
  new Intl.NumberFormat(APP_CONFIG.locale).format(toNumber(value));

/** Stock counts. Whole units stay whole so 20.000 displays as 20, not 20,000. */
export const formatQuantity = (value: unknown): string =>
  new Intl.NumberFormat(APP_CONFIG.locale, {
    minimumFractionDigits: 0,
    maximumFractionDigits: 3,
  }).format(toNumber(value));

export const formatDate = (
  value: string | number | Date | null | undefined,
  template = 'DD MMM YYYY',
): string => {
  if (!value) return '-';
  const parsed = dayjs(value);
  return parsed.isValid() ? parsed.format(template) : '-';
};

export const formatDateTime = (
  value: string | number | Date | null | undefined,
): string => formatDate(value, 'DD MMM YYYY, HH:mm');

export const formatPercent = (value: number | null | undefined): string =>
  `${((typeof value === 'number' ? value : 0) * 100).toFixed(1)}%`;
