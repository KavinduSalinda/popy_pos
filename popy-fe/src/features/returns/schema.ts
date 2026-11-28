import { z } from 'zod';
import { requiredNumber, requiredText } from '@/utils';

const quantityField = z.union([z.number(), z.literal('')]);

export const buildSalesReturnSchema = (limits: {
  ready: boolean;
  match: 'sale' | 'product' | null;
  quantityLeft: number;
  refundLeft: number;
}) =>
  z
    .object({
      code: requiredText('Bill, barcode, or SKU', 120),
      reason: requiredText('Reason', 255),
      refundAmount: requiredNumber(0),
      quantity: quantityField,
    })
    .superRefine((values, ctx) => {
      if (!limits.ready) return;
      if (values.refundAmount > limits.refundLeft) {
        ctx.addIssue({
          code: 'custom',
          path: ['refundAmount'],
          message: `Cannot be more than ${limits.refundLeft}`,
        });
      }
      if (limits.match !== 'product') return;
      if (values.quantity === '' || !(values.quantity > 0)) {
        ctx.addIssue({
          code: 'custom',
          path: ['quantity'],
          message: 'Enter a quantity',
        });
        return;
      }
      if (values.quantity > limits.quantityLeft) {
        ctx.addIssue({
          code: 'custom',
          path: ['quantity'],
          message: `Cannot be more than ${limits.quantityLeft}`,
        });
      }
    });

export type SalesReturnFormInput = z.input<ReturnType<typeof buildSalesReturnSchema>>;
export type SalesReturnFormValues = z.output<ReturnType<typeof buildSalesReturnSchema>>;

export const purchaseReturnSchema = z.object({
  purchaseId: requiredText('Purchase reference', 64),
  reason: requiredText('Reason', 255),
  amount: requiredNumber(0),
});

export const buildPurchaseReturnSchema = (maxAmount?: number) =>
  purchaseReturnSchema.superRefine((values, ctx) => {
    if (maxAmount != null && values.amount > maxAmount) {
      ctx.addIssue({
        code: 'custom',
        path: ['amount'],
        message: `Cannot be more than ${maxAmount}`,
      });
    }
  });

export type PurchaseReturnFormInput = z.input<typeof purchaseReturnSchema>;
export type PurchaseReturnFormValues = z.output<typeof purchaseReturnSchema>;
