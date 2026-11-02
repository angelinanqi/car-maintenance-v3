export function request(
  path: string,
  options?: { method?: string; body?: unknown; signal?: AbortSignal; timeoutMs?: number },
): Promise<any>;
export function listAll(
  path: string,
  filters?: Record<string, string>,
  options?: { timeoutMs?: number },
): Promise<any[]>;
export function setRequestIdentity(value: string): void;
