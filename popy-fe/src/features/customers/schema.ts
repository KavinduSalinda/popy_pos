import { z } from 'zod';
import { optionalEmail, optionalText, requiredInt, requiredPhone, requiredText } from '@/utils';

export const customerSchema = z.object({
  name: requiredText('Name', 120),
  phone: requiredPhone(),
  email: optionalEmail(),
  address: optionalText(255),
  loyaltyPoints: requiredInt(0, 'Must be 0 or more'),
});

export type CustomerFormInput = z.input<typeof customerSchema>;
export type CustomerFormValues = z.output<typeof customerSchema>;
