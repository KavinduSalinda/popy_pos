import { useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Alert, Box, Button, Link, Stack } from '@mui/material';
import { Link as RouterLink, Navigate, useLocation, useNavigate } from 'react-router-dom';
import { FormTextField } from '@/components/forms';
import { Loader } from '@/components/common';
import { useLoginMutation } from '../authApi';
import { loginSchema, type LoginFormValues } from '../schemas';
import { getErrorMessage } from '@/utils';
import { PERMISSIONS, resolveRolePermissions, ROUTES } from '@/constants';
import { defaultAppPath } from '@/app/routes/navigation';
import { getApiBaseUrl } from '@/services/serverConfig';

interface LocationState {
  from?: string;
}

export const LoginPage = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const [login, { isLoading, error }] = useLoginMutation();

  const [setupGate, setSetupGate] = useState<'checking' | 'needed' | 'ready'>('checking');
  const { control, handleSubmit } = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: '', password: '' },
  });

  useEffect(() => {
    let cancelled = false;
    fetch(`${getApiBaseUrl()}/health`)
      .then((response) => (response.ok ? response.json() : null))
      .then((data: { needsSetup?: boolean } | null) => {
        if (cancelled) return;
        setSetupGate(data?.needsSetup ? 'needed' : 'ready');
      })
      .catch(() => {
        if (!cancelled) setSetupGate('ready');
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const onSubmit = handleSubmit(async (values) => {
    try {
      const session = await login(values).unwrap();
      const allowed = new Set(
        resolveRolePermissions(session.user.role, session.user.permissions ?? []),
      );
      const home = defaultAppPath((permission) => allowed.has(permission));
      const state = location.state as LocationState | null;
      const from = state?.from;
      const requested =
        from && from !== ROUTES.HOME && from !== ROUTES.LOGIN ? from : home;
      const next =
        requested === ROUTES.DASHBOARD && !allowed.has(PERMISSIONS.DASHBOARD_VIEW)
          ? home
          : requested;
      navigate(next, { replace: true });
    } catch {
      /* error surfaced via the `error` state */
    }
  });

  if (setupGate === 'checking') return <Loader message="Checking this computer…" />;
  if (setupGate === 'needed') return <Navigate to={ROUTES.SETUP} replace />;

  return (
    <Box component="form" onSubmit={onSubmit} noValidate>
      <Stack spacing={2}>
        {error && <Alert severity="error">{getErrorMessage(error)}</Alert>}
        <FormTextField
          name="email"
          control={control}
          label="Email"
          type="email"
          autoComplete="email"
          autoFocus
        />
        <FormTextField
          name="password"
          control={control}
          label="Password"
          type="password"
          autoComplete="current-password"
        />
        <Box sx={{ textAlign: 'right' }}>
          <Link
            component={RouterLink}
            to={ROUTES.FORGOT_PASSWORD}
            variant="body2"
            underline="hover"
          >
            Forgot password?
          </Link>
        </Box>
        <Button type="submit" variant="contained" size="large" disabled={isLoading}>
          {isLoading ? 'Signing in…' : 'Sign in'}
        </Button>
      </Stack>
    </Box>
  );
};

export default LoginPage;
