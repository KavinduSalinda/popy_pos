import { z } from 'zod';

export const salesReturnSchema = z.object({
  saleId: z.string().trim().min(1, 'Sale reference is required'),
  reason: z.string().min(1, 'Reason is required').max(255),
  refundAmount: z.number().min(0, 'Must be 0 or more'),
});
export type SalesReturnFormValues = z.infer<typeof salesReturnSchema>;

export const purchaseReturnSchema = z.object({
  purchaseId: z.string().trim().min(1, 'Purchase reference is required'),
  reason: z.string().min(1, 'Reason is required').max(255),
  amount: z.number().min(0, 'Must be 0 or more'),
});
export type PurchaseReturnFormValues = z.infer<typeof purchaseReturnSchema>;
