import { useOfflineSyncContext } from './useOfflineSyncContext';
import { useOnlineStatus } from './useOnlineStatus';

export const useOfflineSync = () => {
  const { isOnline } = useOnlineStatus();
  return { isOnline, ...useOfflineSyncContext() };
};
