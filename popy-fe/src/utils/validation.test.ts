import { describe, expect, it } from 'vitest';
import { zodResolver } from '@hookform/resolvers/zod';
import { supplierSchema } from '@/features/suppliers/schema';
import { buildPurchaseReturnSchema, buildSalesReturnSchema } from '@/features/returns/schema';
import {
  customApiUrl,
  optionalEmail,
  optionalText,
  parseAmountPaid,
  requiredEmail,
  requiredNumber,
  requiredPhone,
  requiredText,
} from './validation';

describe('text validation', () => {
  it('rejects a required field that is only spaces', () => {
    const parsed = requiredText('Name', 120).safeParse('   ');
    expect(parsed.success).toBe(false);
    if (!parsed.success) {
      expect(parsed.error.issues[0]?.message).toBe('Name is required');
    }
  });

  it('stores an optional field of only spaces as empty', () => {
    const parsed = optionalText(120).safeParse('   ');
    expect(parsed.success).toBe(true);
    if (parsed.success) expect(parsed.data).toBe('');
  });

  it('trims a real value before it is saved', () => {
    const parsed = requiredText('Name', 120).safeParse('  Tea  ');
    expect(parsed.success).toBe(true);
    if (parsed.success) expect(parsed.data).toBe('Tea');
  });
});

describe('phone and email', () => {
  it('accepts stored phone formats and rejects spaces', () => {
    expect(requiredPhone().safeParse('0121555000').success).toBe(true);
    expect(requiredPhone().safeParse('94771234567').success).toBe(true);
    expect(requiredPhone().safeParse('+94 77 123 4567').success).toBe(true);
    expect(requiredPhone().safeParse('     ').success).toBe(false);
    expect(requiredPhone().safeParse('abcde').success).toBe(false);
  });

  it('rejects a blank or invalid email and trims a valid one', () => {
    expect(requiredEmail().safeParse('   ').success).toBe(false);
    expect(requiredEmail().safeParse('not-an-email').success).toBe(false);
    const parsed = requiredEmail().safeParse('  a@b.com ');
    expect(parsed.success).toBe(true);
    if (parsed.success) expect(parsed.data).toBe('a@b.com');
    expect(optionalEmail().safeParse('   ').data).toBe('');
    expect(optionalEmail().safeParse('nope').success).toBe(false);
  });
});

describe('numbers and urls', () => {
  it('rejects an empty number', () => {
    const parsed = requiredNumber(0).safeParse('');
    expect(parsed.success).toBe(false);
    if (!parsed.success) {
      expect(parsed.error.issues[0]?.message).toBe('Enter a number');
    }
  });

  it('rejects a custom server url that is only spaces or missing /api', () => {
    expect(customApiUrl.safeParse('   ').success).toBe(false);
    expect(customApiUrl.safeParse('http://localhost:8000').success).toBe(false);
    expect(customApiUrl.safeParse('  http://localhost:8000/api ').success).toBe(true);
  });

  it('rejects a spaces-only amount and keeps an untouched total', () => {
    expect(parseAmountPaid('   ', 10)).toEqual({
      ok: false,
      message: 'Enter an amount of 0 or more',
    });
    expect(parseAmountPaid('', 10)).toEqual({ ok: true, value: 10 });
    expect(parseAmountPaid(' 4.5 ', 10)).toEqual({ ok: true, value: 4.5 });
  });
});

describe('supplier form', () => {
  const emptyOptional = {
    companyName: '   ',
    email: '   ',
    address: '   ',
  };

  it('does not accept spaces as a name or phone', async () => {
    const parsed = supplierSchema.safeParse({
      name: '   ',
      phone: '     ',
      ...emptyOptional,
    });
    expect(parsed.success).toBe(false);

    const resolved = await zodResolver(supplierSchema)(
      { name: '   ', phone: '     ', ...emptyOptional },
      undefined,
      { fields: {}, shouldUseNativeValidation: false },
    );
    expect(resolved.values).toEqual({});
    expect(resolved.errors).toMatchObject({
      name: { message: 'Name is required' },
      phone: { message: 'Phone is required' },
    });
  });

  it('rejects a spaces-only return reason and a quantity above what is left', () => {
    const sales = buildSalesReturnSchema({
      ready: true,
      match: 'product',
      quantityLeft: 2,
      refundLeft: 10,
    });
    expect(
      sales.safeParse({ code: '   ', reason: '   ', refundAmount: 1, quantity: 1 }).success,
    ).toBe(false);
    expect(
      sales.safeParse({ code: 'SL-1', reason: 'Broken', refundAmount: 11, quantity: 1 }).success,
    ).toBe(false);
    expect(
      sales.safeParse({ code: 'SL-1', reason: 'Broken', refundAmount: 4, quantity: 3 }).success,
    ).toBe(false);
    expect(
      sales.safeParse({ code: ' SL-1 ', reason: ' Broken ', refundAmount: 4, quantity: 1 }).success,
    ).toBe(true);

    const purchase = buildPurchaseReturnSchema(20);
    expect(
      purchase.safeParse({ purchaseId: '   ', reason: 'Damaged', amount: 5 }).success,
    ).toBe(false);
    expect(
      purchase.safeParse({ purchaseId: 'PO-1', reason: 'Damaged', amount: 21 }).success,
    ).toBe(false);
  });

  it('saves optional spaces as empty and trims the required fields', () => {
    const parsed = supplierSchema.safeParse({
      name: '  Malini  ',
      phone: ' 0121555000 ',
      ...emptyOptional,
    });
    expect(parsed.success).toBe(true);
    if (parsed.success) {
      expect(parsed.data).toMatchObject({
        name: 'Malini',
        phone: '0121555000',
        companyName: '',
        email: '',
        address: '',
      });
    }
  });
});
