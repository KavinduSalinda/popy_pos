import { z } from 'zod';

export const ADJUSTMENT_TYPES = [
  { value: 'DAMAGE', label: 'Damage' },
  { value: 'LOSS', label: 'Loss' },
  { value: 'EXPIRE', label: 'Expire' },
  { value: 'FOUND', label: 'Found' },
  { value: 'ADD', label: 'Add' },
] as const;

const DECREASE_ADJUSTMENT_TYPES = ['DAMAGE', 'LOSS', 'EXPIRE'] as const;

export type AdjustmentTypeValue = (typeof ADJUSTMENT_TYPES)[number]['value'];

export const isDecreaseAdjustment = (type: string) =>
  (DECREASE_ADJUSTMENT_TYPES as readonly string[]).includes(type);

export const roundStock = (value: number) => Math.round(value * 1000) / 1000;

/** Positive quantity. Damage, loss, and expire remove it; found and add increase it. */
export const signedAdjustment = (type: string, quantity: number) => {
  const amount = Math.abs(quantity);
  return isDecreaseAdjustment(type) ? -amount : amount;
};

export const adjustmentSchema = z.object({
  productId: z.union([z.string(), z.number()]).refine((v) => v !== '', {
    message: 'Product is required',
  }),
  adjustmentType: z.enum(['DAMAGE', 'LOSS', 'EXPIRE', 'FOUND', 'ADD']),
  quantity: z.number().positive('Quantity must be greater than 0'),
  newTotal: z.number().min(0, 'Must be 0 or more'),
  note: z.string().max(255).optional().or(z.literal('')),
});

export type AdjustmentFormValues = z.infer<typeof adjustmentSchema>;
