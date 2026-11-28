import { formatQuantity, toNumber } from '@/utils';
import type { RequirementRow } from './types';

export type HorizonDays = 7 | 30 | 90;

export type AdviceTone = 'error' | 'warning' | 'success' | 'default';

export interface RequirementReading {
  expectedSales: number;
  toOrder: number;
  sellingPace: string;
  stockLasts: string;
  /** Days of stock left. Large when the product has stock but no recent sales. */
  coverDays: number;
  advice: string;
  tone: AdviceTone;
  /** The two periods that are not selected, in plain words. */
  otherPeriods: string;
}

const NOT_SELLING_DAYS = 100_000;

const aboutRate = (amount: number, period: 'day' | 'week' | 'month'): string => {
  const rounded = amount >= 10 ? Math.round(amount) : Math.round(amount * 10) / 10;
  return `About ${formatQuantity(rounded)} a ${period}`;
};

export const sellingPace = (perDay: number, sold: number): string => {
  if (sold <= 0 || perDay <= 0) return 'No recent sales';
  if (perDay >= 1) return aboutRate(perDay, 'day');
  const perWeek = perDay * 7;
  if (perWeek >= 2) return aboutRate(perWeek, 'week');
  const perMonth = perDay * 30;
  if (perMonth >= 1) return aboutRate(perMonth, 'month');
  return 'Sells rarely';
};

export const stockLastsLabel = (
  stock: number,
  perDay: number,
): { label: string; coverDays: number } => {
  if (stock <= 0) return { label: 'Out of stock', coverDays: 0 };
  if (perDay <= 0) return { label: 'Not selling', coverDays: NOT_SELLING_DAYS };
  const days = stock / perDay;
  if (days < 1) return { label: 'Less than a day', coverDays: days };
  if (days < 14) {
    const rounded = Math.max(1, Math.round(days));
    return {
      label: rounded === 1 ? 'About 1 day' : `About ${rounded} days`,
      coverDays: days,
    };
  }
  if (days < 56) {
    const weeks = Math.max(2, Math.round(days / 7));
    return { label: `About ${weeks} weeks`, coverDays: days };
  }
  if (days < 365) {
    const months = Math.max(2, Math.round(days / 30));
    return { label: `About ${months} months`, coverDays: days };
  }
  return { label: 'More than a year', coverDays: days };
};

const PERIOD_LABEL: Record<HorizonDays, string> = {
  7: 'Week',
  30: 'Month',
  90: '3 months',
};

export const otherPeriods = (row: RequirementRow, horizon: HorizonDays): string =>
  ([7, 30, 90] as const)
    .filter((days) => days !== horizon)
    .map((days) => {
      const buy = toNumber(row[`buy${days}`]);
      return buy > 0
        ? `${PERIOD_LABEL[days]}: order ${formatQuantity(buy)}`
        : `${PERIOD_LABEL[days]}: covered`;
    })
    .join(' · ');

export const readRequirement = (
  row: RequirementRow,
  horizon: HorizonDays,
): RequirementReading => {
  const stock = toNumber(row.stock);
  const sold = toNumber(row.soldLast30);
  const perDay = toNumber(row.perDay);
  const expectedSales = toNumber(row[`need${horizon}`]);
  const toOrder = toNumber(row[`buy${horizon}`]);
  const lasts = stockLastsLabel(stock, perDay);

  let advice = 'Enough stock';
  let tone: AdviceTone = 'success';
  if (sold <= 0 && toOrder <= 0) {
    advice = 'Not selling';
    tone = 'default';
  } else if (toOrder > 0 && stock <= 0) {
    advice = 'Order now';
    tone = 'error';
  } else if (toOrder > 0 && lasts.coverDays < 7) {
    advice = 'Order soon';
    tone = 'warning';
  } else if (toOrder > 0) {
    advice = 'Order more';
    tone = 'warning';
  }

  return {
    expectedSales,
    toOrder,
    sellingPace: sellingPace(perDay, sold),
    stockLasts: lasts.label,
    coverDays: lasts.coverDays,
    advice,
    tone,
    otherPeriods: otherPeriods(row, horizon),
  };
};
