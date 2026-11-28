import { useEffect, useMemo, useRef } from 'react';
import { useForm, useWatch } from 'react-hook-form';
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
  isDecreaseAdjustment,
  roundStock,
  signedAdjustment,
  type AdjustmentFormInput,
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

  const products = data?.data ?? [];

  const productOptions = useMemo(() => {
    const options = products
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
  }, [products, item]);

  const { control, handleSubmit, reset, setValue, setError } = useForm<
    AdjustmentFormInput,
    unknown,
    AdjustmentFormValues
  >({
      resolver: zodResolver(adjustmentSchema),
      defaultValues: {
        productId: '',
        adjustmentType: 'DAMAGE',
        quantity: 0,
        newTotal: 0,
        note: '',
      },
    });

  const productId = useWatch({ control, name: 'productId' });
  const adjustmentType = useWatch({ control, name: 'adjustmentType' });
  const quantity = useWatch({ control, name: 'quantity' });
  const newTotal = useWatch({ control, name: 'newTotal' });

  const onHand = useMemo(() => {
    if (item && String(productId) === String(item.productId)) {
      return Number(item.stockQuantity) || 0;
    }
    const product = products.find((p) => String(p.id) === String(productId));
    return Number(product?.stockQuantity) || 0;
  }, [item, productId, products]);

  const linked = useRef({
    quantity: 0 as number | '',
    newTotal: 0 as number | '',
    adjustmentType: 'DAMAGE',
    onHand: 0,
  });
  const pendingReset = useRef<{
    productId: AdjustmentFormValues['productId'];
    adjustmentType: AdjustmentFormValues['adjustmentType'];
    quantity: number;
    newTotal: number;
  } | null>(null);

  useEffect(() => {
    if (!open) {
      pendingReset.current = null;
      return;
    }
    const starting = Number(item?.stockQuantity) || 0;
    const next = {
      productId: item?.productId ?? '',
      adjustmentType: 'DAMAGE' as const,
      quantity: 0,
      newTotal: starting,
    };
    pendingReset.current = next;
    linked.current = {
      quantity: 0,
      newTotal: starting,
      adjustmentType: 'DAMAGE',
      onHand: starting,
    };
    reset({ ...next, note: '' });
  }, [open, item, reset]);

  useEffect(() => {
    if (!open) return;
    const pending = pendingReset.current;
    if (pending) {
      const applied =
        productId === pending.productId &&
        adjustmentType === pending.adjustmentType &&
        quantity === pending.quantity &&
        newTotal === pending.newTotal;
      if (!applied) return;
      pendingReset.current = null;
      linked.current = { quantity, newTotal, adjustmentType, onHand };
      return;
    }
    const last = linked.current;
    const qtyChanged = quantity !== last.quantity;
    const totalChanged = newTotal !== last.newTotal;
    const typeChanged = adjustmentType !== last.adjustmentType;
    const handChanged = onHand !== last.onHand;

    if (totalChanged && !qtyChanged && !typeChanged && !handChanged) {
      if (typeof newTotal !== 'number' || !Number.isFinite(newTotal)) {
        linked.current = { quantity, newTotal, adjustmentType, onHand };
        return;
      }
      const nextQty = roundStock(Math.abs(newTotal - onHand));
      linked.current = {
        quantity: nextQty,
        newTotal,
        adjustmentType,
        onHand,
      };
      if (quantity !== nextQty) {
        setValue('quantity', nextQty, { shouldValidate: false, shouldDirty: true });
      }
      return;
    }

    if (
      (qtyChanged || typeChanged || handChanged) &&
      typeof quantity === 'number' &&
      Number.isFinite(quantity)
    ) {
      const next = roundStock(onHand + signedAdjustment(adjustmentType, quantity));
      linked.current = {
        quantity,
        newTotal: next,
        adjustmentType,
        onHand,
      };
      if (newTotal !== next) {
        setValue('newTotal', next, { shouldValidate: false, shouldDirty: true });
      }
      return;
    }

    linked.current = { quantity, newTotal, adjustmentType, onHand };
  }, [open, quantity, newTotal, adjustmentType, onHand, setValue]);

  const onSubmit = handleSubmit(async (values) => {
    const decrease = isDecreaseAdjustment(values.adjustmentType);
    if (decrease && values.newTotal > onHand) {
      setError('newTotal', {
        message: 'Damage, loss, and expire cannot raise the total',
      });
      return;
    }
    if (!decrease && values.newTotal < onHand) {
      setError('newTotal', {
        message: 'Found and add cannot lower the total',
      });
      return;
    }

    const payload: AdjustmentPayload = {
      productId: values.productId,
      adjustmentType: values.adjustmentType as AdjustmentType,
      quantity: Math.abs(values.quantity),
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

  const productSelected = productId !== '' && productId != null;

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
        {productSelected && (
          <Typography variant="body2" color="text.secondary">
            On hand: {formatQuantity(onHand)}
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
          label="Quantity"
          type="number"
          helperText="Damage, loss, and expire remove this amount. Found and add increase it."
        />
        <FormTextField
          name="newTotal"
          control={control}
          label="New total"
          type="number"
          helperText="The on-hand count after this adjustment."
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
