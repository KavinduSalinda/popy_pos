import { useContext } from 'react';
import { OfflineSyncContext } from '../offlineSyncContext';

export const useOfflineSyncContext = () => useContext(OfflineSyncContext);
