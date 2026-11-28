import { z } from 'zod';
import { optionalEmail, optionalText, requiredPhone, requiredText } from '@/utils';

export const supplierSchema = z.object({
  name: requiredText('Name', 120),
  companyName: optionalText(120),
  phone: requiredPhone(),
  email: optionalEmail(),
  address: optionalText(255),
});

export type SupplierFormValues = z.infer<typeof supplierSchema>;
