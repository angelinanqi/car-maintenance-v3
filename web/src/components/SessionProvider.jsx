"use client";

import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { currentAccount, loginAccount, logoutAccount } from "@/api/accounts.mjs";
import { setCsrfToken } from "@/api/client.mjs";

const SessionContext = createContext(null);

export function SessionProvider({ children }) {
  const [identity, setIdentity] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const generation = useRef(0);
  const apply = useCallback((result) => {
    setCsrfToken(result?.csrf_token);
    setIdentity(result);
  }, []);
  const restore = useCallback(async () => {
    const version = ++generation.current;
    setLoading(true);
    try {
      const result = await currentAccount();
      if (version !== generation.current) return;
      apply(result);
      setError("");
    } catch (cause) {
      if (version !== generation.current) return;
      if (cause.status === 401) apply(null);
      else setError(cause.message);
    } finally { if (version === generation.current) setLoading(false); }
  }, [apply]);
  useEffect(() => {
    let active = true;
    Promise.resolve().then(() => { if (active) restore(); });
    const expired = () => { generation.current++; apply(null); setError(""); setLoading(false); };
    window.addEventListener("session-expired", expired);
    return () => { active = false; window.removeEventListener("session-expired", expired); };
  }, [apply, restore]);
  async function login(details) {
    generation.current++;
    await loginAccount(details);
    const result = await currentAccount();
    apply(result);
    setError("");
    setLoading(false);
    return result;
  }
  async function logout() {
    generation.current++;
    await logoutAccount();
    apply(null);
    setError("");
  }
  useEffect(() => {
    if (!identity?.expires_at) return;
    const timer = setTimeout(() => { generation.current++; apply(null); }, Math.max(0, new Date(identity.expires_at).getTime() - Date.now()));
    return () => clearTimeout(timer);
  }, [identity, apply]);
  return <SessionContext.Provider value={{ user: identity?.user, expiresAt: identity?.expires_at, loading, error, restore, login, logout }}>{children}</SessionContext.Provider>;
}

export const useSession = () => useContext(SessionContext);
