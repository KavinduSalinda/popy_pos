import type { ID } from '@/types';

export interface ReturnItemPayload {
  productId: ID;
  quantity: number;
}

export interface SalesReturnLookup {
  match: 'sale' | 'product';
  saleId: number;
  saleReference: string;
  productId?: number;
  productName?: string;
  sku?: string;
  barcode?: string | null;
  quantityLeft: number;
  suggestedQuantity: number;
  suggestedRefund: number;
  refundLeft: number;
}

export interface SalesReturnPayload {
  /** Numeric sale id or receipt reference. Optional when `code` is sent. */
  saleId?: ID | string;
  /** Bill reference, barcode, or SKU. Resolved again when the return is saved. */
  code?: string;
  reason: string;
  items?: ReturnItemPayload[];
  refundAmount: number;
  quantity?: number;
}

export interface PurchaseReturnPayload {
  /** Numeric purchase id or purchase reference. */
  purchaseId: ID | string;
  reason: string;
  items: ReturnItemPayload[];
  amount: number;
}

export interface ReturnRecord {
  id: ID;
  reference: string;
  type: 'SALES' | 'PURCHASE';
  reason: string;
  amount: number;
  createdAt: string;
}
