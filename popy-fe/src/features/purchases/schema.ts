import { z } from 'zod';
import { optionalText, requiredInt, requiredNumber } from '@/utils';

export const purchaseItemSchema = z.object({
  productId: z.union([z.string(), z.number()]).refine((value) => String(value).trim() !== '', {
    message: 'Required',
  }),
  quantity: requiredInt(1, 'Min 1'),
  costPrice: requiredNumber(0, 'Min 0'),
});

export const purchaseSchema = z.object({
  supplierId: z.union([z.string(), z.number()]).refine((value) => String(value).trim() !== '', {
    message: 'Supplier is required',
  }),
  status: z.enum(['DRAFT', 'ORDERED', 'RECEIVED']).optional(),
  note: optionalText(255),
  items: z.array(purchaseItemSchema).min(1, 'Add at least one item'),
});

export type PurchaseFormInput = z.input<typeof purchaseSchema>;
export type PurchaseFormValues = z.output<typeof purchaseSchema>;
