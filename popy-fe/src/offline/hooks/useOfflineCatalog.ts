import { useCallback, useEffect, useState } from 'react';
import { useAppSelector } from '@/app/hooks';
import type { PosProduct } from '@/features/sales/types';
import { searchCachedProducts } from '../catalogCache';
import { useOnlineStatus } from './useOnlineStatus';

export const useOfflineCatalog = (search: string) => {
  const { isOnline } = useOnlineStatus();
  const shopId = useAppSelector((state) => state.auth.currentShopId);
  const [products, setProducts] = useState<PosProduct[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  const loadOfflineProducts = useCallback(async () => {
    if (!shopId) return;
    setIsLoading(true);
    try {
      const rows = await searchCachedProducts(shopId, search);
      setProducts(rows);
    } finally {
      setIsLoading(false);
    }
  }, [search, shopId]);

  useEffect(() => {
    if (isOnline || !shopId) return;
    let cancelled = false;
    void searchCachedProducts(shopId, search).then((rows) => {
      if (!cancelled) {
        setProducts(rows);
        setIsLoading(false);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [isOnline, shopId, search]);

  return {
    offlineProducts: products,
    offlineLoading: isLoading,
    reloadOfflineProducts: loadOfflineProducts,
  };
};
