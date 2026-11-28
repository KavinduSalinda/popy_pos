import { z } from 'zod';

const numberOrBlank = z.union([z.number(), z.literal('')]);

const checkedNumber = (
  check: (value: number, ctx: z.RefinementCtx) => void,
) =>
  numberOrBlank
    .superRefine((value, ctx) => {
      if (value === '') {
        ctx.addIssue({ code: 'custom', message: 'Enter a number' });
        return;
      }
      check(value, ctx);
    })
    .transform((value) => (typeof value === 'number' ? value : 0));

/** Trim, then require at least one non-space character. */
export const requiredText = (label: string, max: number) =>
  z
    .string()
    .trim()
    .min(1, `${label} is required`)
    .max(max, `Must be at most ${max} characters`);

/** Trim. Spaces-only becomes an empty string and is allowed. */
export const optionalText = (max: number) =>
  z
    .string()
    .trim()
    .max(max, `Must be at most ${max} characters`);

export const requiredEmail = () =>
  z
    .string()
    .trim()
    .min(1, 'Email is required')
    .max(255, 'Must be at most 255 characters')
    .refine((value) => z.email().safeParse(value).success, 'Enter a valid email');

export const optionalEmail = () =>
  z
    .string()
    .trim()
    .max(255, 'Must be at most 255 characters')
    .refine(
      (value) => value === '' || z.email().safeParse(value).success,
      'Enter a valid email',
    );

/** 7–15 digits. Spaces, dashes, and a leading + are allowed. */
export const requiredPhone = (max = 20) =>
  z
    .string()
    .trim()
    .min(1, 'Phone is required')
    .max(max, `Must be at most ${max} characters`)
    .refine((value) => {
      if (!/^\+?[\d\s-]+$/.test(value)) return false;
      const digits = value.replace(/\D/g, '');
      return digits.length >= 7 && digits.length <= 15;
    }, 'Enter a valid phone number');

export const requiredPassword = (min: number) =>
  z
    .string()
    .trim()
    .min(min, `Password must be at least ${min} characters`);

/** Empty is allowed. A non-empty password must meet the minimum length. */
export const optionalPassword = (min: number) =>
  z
    .string()
    .trim()
    .refine(
      (value) => value === '' || value.length >= min,
      `Password must be at least ${min} characters`,
    );

export const requiredNumber = (min: number, tooSmall = 'Must be 0 or more') =>
  checkedNumber((value, ctx) => {
    if (value < min) ctx.addIssue({ code: 'custom', message: tooSmall });
  });

export const requiredInt = (min: number, tooSmall = 'Min 1') =>
  checkedNumber((value, ctx) => {
    if (!Number.isInteger(value)) {
      ctx.addIssue({ code: 'custom', message: 'Enter a whole number' });
      return;
    }
    if (value < min) ctx.addIssue({ code: 'custom', message: tooSmall });
  });

export const positiveNumber = (tooSmall = 'Quantity must be greater than 0') =>
  checkedNumber((value, ctx) => {
    if (value <= 0) ctx.addIssue({ code: 'custom', message: tooSmall });
  });

export const customApiUrl = z
  .string()
  .trim()
  .min(1, 'Server URL is required')
  .refine(
    (value) => /^https?:\/\//i.test(value) && value.endsWith('/api'),
    'Must start with http:// or https:// and end with /api',
  );

/** Typed amount, or the sale total when the box was left untouched. */
export const parseAmountPaid = (
  typed: string,
  fallback: number,
): { ok: true; value: number } | { ok: false; message: string } => {
  if (typed !== '' && typed.trim() === '') {
    return { ok: false, message: 'Enter an amount of 0 or more' };
  }
  const raw = typed === '' ? String(fallback) : typed.trim();
  const value = Number(raw);
  if (!Number.isFinite(value) || value < 0) {
    return { ok: false, message: 'Enter an amount of 0 or more' };
  }
  return { ok: true, value };
};
