/**
 * Token persistence, isolated in one module. If this ever needs to move to
 * an httpOnly cookie (recommended for production hardening), this is the
 * only file that changes — every call site just imports getToken/setToken.
 */
const TOKEN_KEY = "talentflow_access_token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(TOKEN_KEY);
}
