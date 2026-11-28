import { z } from 'zod';
import { requiredEmail, requiredPassword, requiredText } from '@/utils';

export const loginSchema = z.object({
  email: requiredEmail(),
  password: requiredPassword(6),
});
export type LoginFormValues = z.infer<typeof loginSchema>;

export const forgotPasswordSchema = z.object({
  email: requiredEmail(),
});
export type ForgotPasswordFormValues = z.infer<typeof forgotPasswordSchema>;

const confirmPassword = z.string().trim().min(1, 'Please confirm your password');

export const desktopSetupSchema = z
  .object({
    shopName: requiredText('Shop name', 120),
    adminName: requiredText('Your name', 120),
    email: requiredEmail(),
    password: requiredPassword(8),
    confirmPassword,
  })
  .refine((data) => data.password === data.confirmPassword, {
    message: 'Passwords do not match',
    path: ['confirmPassword'],
  });
export type DesktopSetupValues = z.infer<typeof desktopSetupSchema>;

export const resetPasswordSchema = z
  .object({
    password: requiredPassword(6),
    confirmPassword,
  })
  .refine((data) => data.password === data.confirmPassword, {
    message: 'Passwords do not match',
    path: ['confirmPassword'],
  });
export type ResetPasswordFormValues = z.infer<typeof resetPasswordSchema>;
