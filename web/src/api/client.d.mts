export function request(
  path: string,
  options?: { method?: string; body?: unknown; signal?: AbortSignal },
): Promise<any>;
export function listAll(
  path: string,
  filters?: Record<string, string>,
): Promise<any[]>;
export function setCsrfToken(value: string): void;
