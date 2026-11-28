import { z } from 'zod';
import { optionalText, requiredText } from '@/utils';

export const categorySchema = z.object({
  name: requiredText('Name', 80),
  description: optionalText(255),
});

export type CategoryFormValues = z.infer<typeof categorySchema>;
