import { describe, expect, it } from 'vitest';
import {
  getRoleOptionsForActor,
  MANAGER_ASSIGNABLE_ROLES,
  ROLE_OPTIONS,
  ROLES,
} from './roles';

describe('getRoleOptionsForActor', () => {
  it('returns all roles for super admin', () => {
    expect(getRoleOptionsForActor(ROLES.SUPER_ADMIN)).toEqual(ROLE_OPTIONS);
  });

  it('returns only assignable roles for managers', () => {
    const options = getRoleOptionsForActor(ROLES.MANAGER);
    expect(options.map((o) => o.value)).toEqual(MANAGER_ASSIGNABLE_ROLES);
  });
});
