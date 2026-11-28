import { z } from 'zod';
import { optionalPassword, requiredEmail, requiredPassword, requiredText } from '@/utils';
import { ROLES } from '@/constants/roles';

const roleValues = Object.values(ROLES) as [string, ...string[]];

const userFields = {
  name: requiredText('Name', 120),
  email: requiredEmail(),
  role: z.enum(roleValues),
  isActive: z.boolean(),
};

export const userCreateSchema = z.object({
  ...userFields,
  password: requiredPassword(6),
});

export const userEditSchema = z.object({
  ...userFields,
  password: optionalPassword(6),
});

export type UserFormValues = z.infer<typeof userCreateSchema>;
