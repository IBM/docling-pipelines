/**
 * Authentication hook stub.
 *
 * Currently returns a hard-coded authenticated state.
 * Replace with a real authentication check (e.g. JWT validation, session ping)
 * once the auth layer is wired.
 */

/** Return shape of {@link useAuth}. */
interface UseAuthReturn {
  /** `true` when the current user has a valid session. */
  isAuthenticated: boolean;
  /** `true` while the auth state is being resolved (e.g. verifying a stored token). */
  isLoading: boolean;
}

/**
 * Returns the current authentication state.
 *
 * Used by {@link ProtectedRoute} to gate access to authenticated pages.
 */
export function useAuth(): UseAuthReturn {
  return { isAuthenticated: true, isLoading: false };
}
