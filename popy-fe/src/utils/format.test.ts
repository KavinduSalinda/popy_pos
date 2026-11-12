import { describe, expect, it } from 'vitest';
import {
  formatCurrency,
  formatDate,
  formatNumber,
  formatPercent,
  formatQuantity,
} from './format';

describe('format utilities', () => {
  it('formats currency with locale', () => {
    expect(formatCurrency(1234.5)).toMatch(/1,234\.50|1\.234,50/);
  });

  it('formats nullish currency as zero', () => {
    expect(formatCurrency(null)).toMatch(/0/);
  });

  it('formats string decimals from API responses', () => {
    expect(formatCurrency('1234.50')).toMatch(/1,234\.50|1\.234,50/);
    expect(formatCurrency('850')).toMatch(/850/);
  });

  it('formats string numbers with grouping', () => {
    expect(formatNumber('10000')).toBe('10,000');
  });

  it('shows stock quantities as units, not thousandths', () => {
    expect(formatQuantity('20.000')).toBe('20');
    expect(formatQuantity('32.000')).toBe('32');
    expect(formatQuantity('1.250')).toBe('1.25');
    expect(formatQuantity(0)).toBe('0');
  });

  it('formats dates', () => {
    expect(formatDate('2024-01-15')).toBe('15 Jan 2024');
  });

  it('returns dash for invalid dates', () => {
    expect(formatDate(null)).toBe('-');
  });

  it('formats percent', () => {
    expect(formatPercent(0.125)).toBe('12.5%');
  });
});
