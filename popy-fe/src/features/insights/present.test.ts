import { describe, expect, it } from 'vitest';
import { readRequirement } from './present';
import type { RequirementRow } from './types';

const tea = (overrides: Partial<RequirementRow> = {}): RequirementRow => ({
  product: 'Green Tea',
  sku: 'TEA-1',
  stock: 10,
  soldLast30: 30,
  perDay: 1,
  need7: 7,
  need30: 30,
  need90: 90,
  buy7: 0,
  buy30: 20,
  buy90: 80,
  ...overrides,
});

describe('readRequirement', () => {
  it('tells you to order more when a month of sales is not covered', () => {
    const reading = readRequirement(tea(), 30);

    expect(reading.sellingPace).toBe('About 1 a day');
    expect(reading.stockLasts).toBe('About 10 days');
    expect(reading.expectedSales).toBe(30);
    expect(reading.toOrder).toBe(20);
    expect(reading.advice).toBe('Order more');
    expect(reading.otherPeriods).toBe('Week: covered · 3 months: order 80');
  });

  it('says the coming week is covered when stock lasts past it', () => {
    const reading = readRequirement(tea(), 7);

    expect(reading.toOrder).toBe(0);
    expect(reading.advice).toBe('Enough stock');
  });

  it('asks for an order now when the shelf is empty', () => {
    const reading = readRequirement(
      tea({ stock: 0, buy7: 7, buy30: 30, buy90: 90 }),
      7,
    );

    expect(reading.stockLasts).toBe('Out of stock');
    expect(reading.advice).toBe('Order now');
    expect(reading.tone).toBe('error');
  });

  it('asks to order soon when only a couple of days of stock remain', () => {
    const reading = readRequirement(tea({ stock: 2, buy7: 5, buy30: 28, buy90: 88 }), 7);

    expect(reading.stockLasts).toBe('About 2 days');
    expect(reading.advice).toBe('Order soon');
  });

  it('says a product with no sales is not selling', () => {
    const reading = readRequirement(
      tea({
        stock: 4,
        soldLast30: 0,
        perDay: 0,
        need7: 0,
        need30: 0,
        need90: 0,
        buy7: 0,
        buy30: 0,
        buy90: 0,
      }),
      30,
    );

    expect(reading.sellingPace).toBe('No recent sales');
    expect(reading.stockLasts).toBe('Not selling');
    expect(reading.expectedSales).toBe(0);
    expect(reading.advice).toBe('Not selling');
  });

  it('describes a slow seller by the week or the month', () => {
    expect(readRequirement(tea({ soldLast30: 15, perDay: 0.5 }), 30).sellingPace).toBe(
      'About 3.5 a week',
    );
    expect(readRequirement(tea({ soldLast30: 6, perDay: 0.2 }), 30).sellingPace).toBe(
      'About 6 a month',
    );
    expect(readRequirement(tea({ soldLast30: 1, perDay: 0.03 }), 30).sellingPace).toBe(
      'Sells rarely',
    );
  });

  it('rounds a fast pace instead of showing long decimals', () => {
    expect(readRequirement(tea({ soldLast30: 62, perDay: 2.067 }), 30).sellingPace).toBe(
      'About 2.1 a day',
    );
  });

  it('says stock will last for weeks, months, or more than a year', () => {
    expect(readRequirement(tea({ stock: 21, perDay: 1 }), 90).stockLasts).toBe('About 3 weeks');
    expect(readRequirement(tea({ stock: 60, perDay: 1 }), 90).stockLasts).toBe('About 2 months');
    expect(readRequirement(tea({ stock: 400, perDay: 1 }), 90).stockLasts).toBe(
      'More than a year',
    );
  });
});
