import { useEffect, useMemo } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Button, Stack, Typography } from '@mui/material';
import { toast } from 'react-toastify';
import { Modal } from '@/components/dialogs';
import { FormSelect, FormTextField } from '@/components/forms';
import { formatQuantity, getErrorMessage } from '@/utils';
import { useGetProductsQuery } from '@/features/products/productsApi';
import { useCreateAdjustmentMutation } from '../inventoryApi';
import {
  ADJUSTMENT_TYPES,
  adjustmentSchema,
  type AdjustmentFormValues,
} from '../schema';
import type {
  AdjustmentPayload,
  AdjustmentType,
  InventoryItem,
} from '../types';

interface AdjustmentDialogProps {
  open: boolean;
  onClose: () => void;
  /** Item chosen from the inventory table. Prefills the product. */
  item?: InventoryItem | null;
}

export const AdjustmentDialog = ({
  open,
  onClose,
  item = null,
}: AdjustmentDialogProps) => {
  const { data } = useGetProductsQuery({
    page: 1,
    pageSize: 100,
    status: 'true',
  });
  const [createAdjustment, { isLoading }] = useCreateAdjustmentMutation();

  const productOptions = useMemo(() => {
    const options = (data?.data ?? [])
      .filter((p) => p.status)
      .map((p) => ({
        value:
          item && String(p.id) === String(item.productId) ? item.productId : p.id,
        label: `${p.name} (${p.sku})`,
      }));

    if (
      item &&
      !options.some((option) => String(option.value) === String(item.productId))
    ) {
      options.unshift({
        value: item.productId,
        label: `${item.productName} (${item.sku})`,
      });
    }

    return options;
  }, [data, item]);

  const { control, handleSubmit, reset } = useForm<AdjustmentFormValues>({
    resolver: zodResolver(adjustmentSchema),
    defaultValues: {
      productId: '',
      adjustmentType: 'DAMAGE',
      quantity: 0,
      note: '',
    },
  });

  useEffect(() => {
    if (open) {
      reset({
        productId: item?.productId ?? '',
        adjustmentType: 'DAMAGE',
        quantity: 0,
        note: '',
      });
    }
  }, [open, item, reset]);

  const onSubmit = handleSubmit(async (values) => {
    const payload: AdjustmentPayload = {
      productId: values.productId,
      adjustmentType: values.adjustmentType as AdjustmentType,
      quantity: values.quantity,
      note: values.note || undefined,
    };
    try {
      await createAdjustment(payload).unwrap();
      toast.success('Stock adjustment recorded');
      onClose();
    } catch (error) {
      toast.error(getErrorMessage(error));
    }
  });

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={item ? `Adjust ${item.productName}` : 'New stock adjustment'}
      actions={
        <>
          <Button color="inherit" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="contained" onClick={onSubmit} disabled={isLoading}>
            Save adjustment
          </Button>
        </>
      }
    >
      <Stack component="form" spacing={2} onSubmit={onSubmit} mt={1}>
        {item && (
          <Typography variant="body2" color="text.secondary">
            On hand: {formatQuantity(item.stockQuantity)}
          </Typography>
        )}
        <FormSelect
          name="productId"
          control={control}
          label="Product"
          options={productOptions}
        />
        <FormSelect
          name="adjustmentType"
          control={control}
          label="Adjustment type"
          options={ADJUSTMENT_TYPES}
        />
        <FormTextField
          name="quantity"
          control={control}
          label="Quantity (use negative to reduce)"
          type="number"
        />
        <FormTextField
          name="note"
          control={control}
          label="Note"
          multiline
          minRows={2}
        />
      </Stack>
    </Modal>
  );
};
