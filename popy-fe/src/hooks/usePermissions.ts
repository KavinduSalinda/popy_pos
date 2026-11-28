import { useMemo } from 'react';
import { useAppSelector } from '@/app/hooks';
import { selectCurrentUser } from '@/features/auth/authSelectors';
import { resolveRolePermissions, type Permission } from '@/constants/permissions';

export interface UsePermissionsResult {
  permissions: Permission[];
  hasPermission: (permission: Permission) => boolean;
  hasAnyPermission: (permissions: Permission[]) => boolean;
  hasAllPermissions: (permissions: Permission[]) => boolean;
}

/**
 * Resolves the current user's effective permissions from their role.
 * A saved permission list cannot add a menu the role map does not grant.
 */
export const usePermissions = (): UsePermissionsResult => {
  const user = useAppSelector(selectCurrentUser);

  const permissions = useMemo<Permission[]>(
    () => (user ? resolveRolePermissions(user.role, user.permissions ?? []) : []),
    [user],
  );

  return useMemo(() => {
    const permissionSet = new Set<Permission>(permissions);
    return {
      permissions,
      hasPermission: (permission) => permissionSet.has(permission),
      hasAnyPermission: (required) =>
        required.length === 0 || required.some((p) => permissionSet.has(p)),
      hasAllPermissions: (required) =>
        required.every((p) => permissionSet.has(p)),
    };
  }, [permissions]);
};
