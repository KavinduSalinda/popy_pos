import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import { useAppSelector } from '@/app/hooks';
import { getQueueSummary } from './queue';
import { bootstrapOfflineData, runFullSync } from './syncEngine';
import { useOnlineStatus } from './hooks/useOnlineStatus';
import { OfflineSyncContext } from './offlineSyncContext';

export const OfflineSyncProvider = ({ children }: { children: ReactNode }) => {
  const { isOnline } = useOnlineStatus();
  const shopId = useAppSelector((state) => state.auth.currentShopId);
  const isAuthenticated = useAppSelector((state) => Boolean(state.auth.user));
  const [isSyncing, setIsSyncing] = useState(false);
  const [pendingCount, setPendingCount] = useState(0);
  const [lastMessage, setLastMessage] = useState<string | null>(null);
  const wasOfflineRef = useRef(!navigator.onLine);

  const refreshCounts = useCallback(async () => {
    if (!shopId) return;
    const summary = await getQueueSummary(shopId);
    setPendingCount(summary.total);
  }, [shopId]);

  const downloadCatalog = useCallback(async () => {
    if (!shopId || !isOnline) return false;
    setIsSyncing(true);
    try {
      await bootstrapOfflineData(shopId);
      await refreshCounts();
      setLastMessage('Offline catalog updated.');
      return true;
    } catch {
      setLastMessage('Failed to download offline catalog.');
      return false;
    } finally {
      setIsSyncing(false);
    }
  }, [isOnline, refreshCounts, shopId]);

  const syncNow = useCallback(async () => {
    if (!shopId || !isOnline) return;
    setIsSyncing(true);
    try {
      const result = await runFullSync(shopId);
      await refreshCounts();
      if (result.rejectedSales > 0) {
        setLastMessage(
          result.message ?? `${result.rejectedSales} sale(s) need review.`,
        );
      } else if (result.syncedSales > 0) {
        setLastMessage(`${result.syncedSales} offline sale(s) synced.`);
      }
    } catch {
      setLastMessage('Sync failed. Will retry when online.');
    } finally {
      setIsSyncing(false);
    }
  }, [isOnline, refreshCounts, shopId]);

  useEffect(() => {
    if (!shopId) return;
    let cancelled = false;
    void getQueueSummary(shopId).then((summary) => {
      if (!cancelled) setPendingCount(summary.total);
    });
    return () => {
      cancelled = true;
    };
  }, [shopId]);

  useEffect(() => {
    if (!isAuthenticated || !isOnline || !shopId) return;
    let cancelled = false;
    void bootstrapOfflineData(shopId)
      .then(() => getQueueSummary(shopId))
      .then((summary) => {
        if (!cancelled) setPendingCount(summary.total);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [isAuthenticated, isOnline, shopId]);

  useEffect(() => {
    const cameOnline = isOnline && wasOfflineRef.current;
    wasOfflineRef.current = !isOnline;
    if (cameOnline && shopId && isAuthenticated) {
      void syncNow();
    }
  }, [isAuthenticated, isOnline, shopId, syncNow]);

  return (
    <OfflineSyncContext.Provider
      value={{
        isSyncing,
        pendingCount,
        lastMessage,
        downloadCatalog,
        syncNow,
        refreshCounts,
      }}
    >
      {children}
    </OfflineSyncContext.Provider>
  );
};
