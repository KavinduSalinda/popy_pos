import { useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Alert, Box, Button, Stack, Typography } from '@mui/material';
import { Navigate, useNavigate } from 'react-router-dom';
import { FormTextField } from '@/components/forms';
import { Loader } from '@/components/common';
import { ROUTES } from '@/constants';
import { getApiBaseUrl } from '@/services/serverConfig';
import { getErrorMessage } from '@/utils';
import { useSetupDesktopMutation } from '../authApi';
import { desktopSetupSchema, type DesktopSetupValues } from '../schemas';

export const SetupPage = () => {
  const navigate = useNavigate();
  const [setupDesktop, { isLoading, error }] = useSetupDesktopMutation();
  const [gate, setGate] = useState<'checking' | 'needed' | 'ready'>('checking');
  const { control, handleSubmit } = useForm<DesktopSetupValues>({
    resolver: zodResolver(desktopSetupSchema),
    defaultValues: {
      shopName: '',
      adminName: '',
      email: '',
      password: '',
      confirmPassword: '',
    },
  });

  useEffect(() => {
    let cancelled = false;
    fetch(`${getApiBaseUrl()}/health`)
      .then((response) => (response.ok ? response.json() : null))
      .then((data: { needsSetup?: boolean } | null) => {
        if (cancelled) return;
        setGate(data?.needsSetup ? 'needed' : 'ready');
      })
      .catch(() => {
        if (!cancelled) setGate('ready');
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const onSubmit = handleSubmit(async (values) => {
    try {
      await setupDesktop({
        shopName: values.shopName,
        adminName: values.adminName,
        email: values.email,
        password: values.password,
      }).unwrap();
      navigate(ROUTES.LOGIN, { replace: true });
    } catch {
      /* shown via the mutation error */
    }
  });

  if (gate === 'checking') return <Loader message="Checking this computer…" />;
  if (gate === 'ready') return <Navigate to={ROUTES.LOGIN} replace />;

  return (
    <Box component="form" onSubmit={onSubmit} noValidate>
      <Stack spacing={2}>
        <Typography variant="body2" color="text.secondary" textAlign="center">
          Create the shop and the first admin account for this computer.
        </Typography>
        {error && <Alert severity="error">{getErrorMessage(error)}</Alert>}
        <FormTextField name="shopName" control={control} label="Shop name" autoFocus />
        <FormTextField name="adminName" control={control} label="Your name" />
        <FormTextField
          name="email"
          control={control}
          label="Email"
          type="email"
          autoComplete="email"
        />
        <FormTextField
          name="password"
          control={control}
          label="Password"
          type="password"
          autoComplete="new-password"
        />
        <FormTextField
          name="confirmPassword"
          control={control}
          label="Confirm password"
          type="password"
          autoComplete="new-password"
        />
        <Button type="submit" variant="contained" size="large" disabled={isLoading}>
          {isLoading ? 'Creating shop…' : 'Create shop'}
        </Button>
      </Stack>
    </Box>
  );
};

export default SetupPage;
