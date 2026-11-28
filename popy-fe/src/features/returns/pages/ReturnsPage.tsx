import { useMemo, useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import {
  Box,
  Button,
  Card,
  CardContent,
  Stack,
  Tab,
  Tabs,
  Typography,
} from '@mui/material';
import { toast } from 'react-toastify';
import { PageHeader } from '@/components/common';
import { FormTextField } from '@/components/forms';
import { formatQuantity, getErrorMessage } from '@/utils';
import {
  useCreatePurchaseReturnMutation,
  useCreateSalesReturnMutation,
  useLazyLookupSalesReturnQuery,
} from '../returnsApi';
import {
  buildSalesReturnSchema,
  purchaseReturnSchema,
  type PurchaseReturnFormInput,
  type PurchaseReturnFormValues,
  type SalesReturnFormInput,
  type SalesReturnFormValues,
} from '../schema';
import type { SalesReturnLookup } from '../types';

type TabKey = 'sales' | 'purchase';

const SalesReturnForm = () => {
  const [createSalesReturn, { isLoading }] = useCreateSalesReturnMutation();
  const [lookupSalesReturn, { isFetching }] = useLazyLookupSalesReturnQuery();
  const [found, setFound] = useState<SalesReturnLookup | null>(null);
  const [foundCode, setFoundCode] = useState('');
  const schema = useMemo(
    () =>
      buildSalesReturnSchema({
        ready: Boolean(found),
        match: found?.match ?? null,
        quantityLeft: found?.quantityLeft ?? 0,
        refundLeft: found?.refundLeft ?? 0,
      }),
    [found],
  );
  const { control, handleSubmit, reset, setValue, getValues, watch } = useForm<
    SalesReturnFormInput,
    unknown,
    SalesReturnFormValues
  >({
    resolver: zodResolver(schema),
    defaultValues: { code: '', reason: '', refundAmount: 0, quantity: '' },
  });

  const runLookup = async (raw: string) => {
    const code = raw.trim();
    if (!code) return;
    try {
      const result = await lookupSalesReturn(code).unwrap();
      setFound(result);
      setFoundCode(code);
      setValue(
        'quantity',
        result.match === 'product' ? result.suggestedQuantity : '',
        { shouldValidate: true },
      );
      setValue('refundAmount', result.suggestedRefund, { shouldValidate: true });
    } catch (error) {
      setFound(null);
      setFoundCode('');
      toast.error(getErrorMessage(error));
    }
  };

  const onSubmit = handleSubmit(async (values) => {
    const code = values.code.trim();
    if (!found || foundCode !== code) {
      toast.error('Find the bill, barcode, or SKU before processing the return.');
      return;
    }
    try {
      await createSalesReturn({
        code,
        reason: values.reason,
        refundAmount: values.refundAmount,
        ...(found.match === 'product'
          ? { quantity: Number(values.quantity) }
          : { items: [] }),
      }).unwrap();
      toast.success('Sales return recorded');
      setFound(null);
      setFoundCode('');
      reset();
    } catch (error) {
      toast.error(getErrorMessage(error));
    }
  });

  const codeValue = watch('code');
  const ready = Boolean(found && foundCode && codeValue.trim() === foundCode);
  const productReturn = ready && found?.match === 'product';

  return (
    <Stack component="form" spacing={2} onSubmit={onSubmit} maxWidth={480}>
      <Stack direction="row" spacing={1} sx={{ alignItems: 'flex-start' }}>
        <FormTextField
          name="code"
          control={control}
          label="Bill, barcode, or SKU"
          placeholder="SL-2026-0060 or scan a barcode"
          helperText="A bill returns what is left on that receipt. A barcode or SKU uses the newest sale that still has that product."
          onKeyDown={(event) => {
            if (event.key === 'Enter') {
              event.preventDefault();
              void runLookup(getValues('code'));
            }
          }}
        />
        <Button
          type="button"
          variant="outlined"
          disabled={isFetching}
          onClick={() => void runLookup(getValues('code'))}
          sx={{ mt: 0.25, flexShrink: 0 }}
        >
          Find
        </Button>
      </Stack>
      {ready && found ? (
        <Box>
          <Typography sx={{ fontWeight: 600 }}>
            {found.productName ? `${found.productName} · ${found.saleReference}` : found.saleReference}
          </Typography>
          <Typography sx={{ color: 'text.secondary', fontSize: 13 }}>
            {productReturn
              ? `${formatQuantity(found.quantityLeft)} left on this sale`
              : `Returning everything left (${formatQuantity(found.quantityLeft)})`}
          </Typography>
        </Box>
      ) : null}
      {productReturn && found ? (
        <FormTextField
          name="quantity"
          control={control}
          label="Quantity"
          type="number"
          helperText={`Up to ${formatQuantity(found.quantityLeft)}`}
          slotProps={{
            htmlInput: {
              min: 0.001,
              max: found.quantityLeft,
              step: 0.001,
            },
          }}
        />
      ) : null}
      <FormTextField
        name="reason"
        control={control}
        label="Reason"
        multiline
        minRows={2}
      />
      <FormTextField
        name="refundAmount"
        control={control}
        label="Refund amount"
        type="number"
        helperText={
          ready && found
            ? `Capped at ${found.refundLeft} still left on the sale`
            : undefined
        }
      />
      <Button
        type="submit"
        variant="contained"
        disabled={isLoading || !ready}
        sx={{ alignSelf: 'flex-start' }}
      >
        Process sales return
      </Button>
    </Stack>
  );
};

const PurchaseReturnForm = () => {
  const [createPurchaseReturn, { isLoading }] =
    useCreatePurchaseReturnMutation();
  const { control, handleSubmit, reset } = useForm<
    PurchaseReturnFormInput,
    unknown,
    PurchaseReturnFormValues
  >({
    resolver: zodResolver(purchaseReturnSchema),
    defaultValues: { purchaseId: '', reason: '', amount: 0 },
  });

  const onSubmit = handleSubmit(async (values) => {
    try {
      await createPurchaseReturn({
        purchaseId: values.purchaseId,
        reason: values.reason,
        amount: values.amount,
        items: [],
      }).unwrap();
      toast.success('Purchase return recorded');
      reset();
    } catch (error) {
      toast.error(getErrorMessage(error));
    }
  });

  return (
    <Stack component="form" spacing={2} onSubmit={onSubmit} maxWidth={480}>
      <FormTextField
        name="purchaseId"
        control={control}
        label="Purchase reference"
        placeholder="e.g. PO-2026-0001"
        helperText="Copy the reference from Purchases. Numeric ID also works."
      />
      <FormTextField
        name="reason"
        control={control}
        label="Reason"
        multiline
        minRows={2}
      />
      <FormTextField
        name="amount"
        control={control}
        label="Return amount"
        type="number"
      />
      <Button
        type="submit"
        variant="contained"
        disabled={isLoading}
        sx={{ alignSelf: 'flex-start' }}
      >
        Process purchase return
      </Button>
    </Stack>
  );
};

export const ReturnsPage = () => {
  const [tab, setTab] = useState<TabKey>('sales');

  return (
    <>
      <PageHeader
        title="Returns"
        subtitle="Process sales and purchase returns"
      />
      <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 2 }}>
        <Tabs value={tab} onChange={(_e, value: TabKey) => setTab(value)}>
          <Tab value="sales" label="Sales Return" />
          <Tab value="purchase" label="Purchase Return" />
        </Tabs>
      </Box>
      <Card>
        <CardContent>
          {tab === 'sales' ? <SalesReturnForm /> : <PurchaseReturnForm />}
        </CardContent>
      </Card>
    </>
  );
};

export default ReturnsPage;
