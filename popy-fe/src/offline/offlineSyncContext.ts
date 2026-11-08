import { createContext } from 'react';

export interface OfflineSyncContextValue {
  isSyncing: boolean;
  pendingCount: number;
  lastMessage: string | null;
  downloadCatalog: () => Promise<boolean>;
  syncNow: () => Promise<void>;
  refreshCounts: () => Promise<void>;
}

export const defaultOfflineSyncContext: OfflineSyncContextValue = {
  isSyncing: false,
  pendingCount: 0,
  lastMessage: null,
  downloadCatalog: async () => false,
  syncNow: async () => undefined,
  refreshCounts: async () => undefined,
};

export const OfflineSyncContext = createContext<OfflineSyncContextValue>(
  defaultOfflineSyncContext,
);
