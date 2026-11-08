import { describe, expect, it } from 'vitest';
import { classifySyncResults, formatConflictMessage } from './conflictResolver';
import type { SalesSyncResult } from './types';

const results: SalesSyncResult[] = [
  { clientId: 'a', status: 'synced' },
  { clientId: 'b', status: 'duplicate' },
  { clientId: 'c', status: 'rejected', message: 'Insufficient stock' },
  { clientId: 'd', status: 'rejected' },
];

describe('conflictResolver', () => {
  it('classifies synced, duplicate, and rejected results', () => {
    const { synced, rejected } = classifySyncResults(results);
    expect(synced).toHaveLength(2);
    expect(rejected).toHaveLength(2);
  });

  it('formats conflict messages for rejected sales', () => {
    expect(formatConflictMessage(results)).toBe(
      'Insufficient stock; Sale d rejected',
    );
    expect(formatConflictMessage([{ clientId: 'x', status: 'synced' }])).toBeNull();
  });
});
