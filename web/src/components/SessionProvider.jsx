"use client";

import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { currentAccount } from "@/api/accounts.mjs";
import { setRequestIdentity } from "@/api/client.mjs";
import { browserAuth, authResult, authError } from "@/lib/supabase.mjs";

const SessionContext = createContext(null);

export function SessionProvider({ children }) {
  const [identity, setIdentity] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [recovering, setRecovering] = useState(false);
  const recoveringRef = useRef(false);
  const identityRef = useRef(null);
  const generation = useRef(0);
  const apply = useCallback((result) => {
    identityRef.current = result;
    setRequestIdentity(result ? `${result.user.id}:${result.expires_at}` : "");
    setIdentity(result);
  }, []);
  const recoveryState = useCallback(value => {
    recoveringRef.current = value;
    setRecovering(value);
    try {
      if (value) sessionStorage.setItem("roadie-recovery", "true");
      else sessionStorage.removeItem("roadie-recovery");
    } catch { /* The verified provider recovery method also survives reload. */ }
  }, []);

  const restore = useCallback(async () => {
    const version = ++generation.current;
    if (!identityRef.current) setLoading(true);
    try {
      const auth = browserAuth();
      const { session } = await authResult(auth.getSession());
      if (!session) {
        if (version !== generation.current) return;
        apply(null);
        setError("");
        return;
      }
      const verified = await authResult(auth.getClaims());
      if (version !== generation.current) return;
      if (verified.claims.amr?.some(method => method.method === "recovery")) recoveryState(true);
      const result = await currentAccount();
      if (version !== generation.current) return;
      apply(result);
      setError("");
      return result;
    } catch (cause) {
      if (version !== generation.current) return;
      apply(null);
      setError(cause.status === 401 ? "" : authError(cause));
    } finally { if (version === generation.current) setLoading(false); }
  }, [apply, recoveryState]);

  useEffect(() => {
    let active = true, auth, subscription;
    const timers = new Set();
    const later = callback => {
      const timer = setTimeout(() => { timers.delete(timer); if (active) callback(); }, 0);
      timers.add(timer);
    };
    try {
      auth = browserAuth();
      subscription = auth.onAuthStateChange((event) => {
        // SDK calls are deferred outside the auth callback's lock.
        if (event === "PASSWORD_RECOVERY") later(() => { recoveryState(true); restore(); });
        else if (event === "SIGNED_OUT") later(() => {
          generation.current++;
          recoveryState(false);
          apply(null);
          setError(""); setLoading(false);
        });
        else if (event !== "INITIAL_SESSION") later(restore);
      }).data.subscription;
    } catch (cause) { setError(authError(cause)); setLoading(false); }
    Promise.resolve().then(async () => {
      if (auth) {
        const result = await auth.initialize();
        if (result.error && active) { setError(authError(result.error)); setLoading(false); return; }
      }
      if (active) restore();
    }).catch(() => { if (active) { setError("Session startup failed. Check browser storage and retry."); setLoading(false); } });
    const expired = () => { generation.current++; apply(null); setError("Your session expired. Sign in again."); setLoading(false); };
    const focus = () => { if (active) restore(); };
    window.addEventListener("session-expired", expired);
    window.addEventListener("focus", focus);
    return () => {
      active = false; subscription?.unsubscribe();
      for (const timer of timers) clearTimeout(timer);
      window.removeEventListener("session-expired", expired);
      window.removeEventListener("focus", focus);
    };
  }, [apply, recoveryState, restore]);

  async function login(details) {
    generation.current++;
    apply(null);
    setError("");
    recoveryState(false);
    await authResult(browserAuth().signInWithPassword(details));
    return restore();
  }

  async function logout() {
    generation.current++;
    await authResult(browserAuth().signOut({ scope: "local" }));
    recoveryState(false);
    apply(null); setError(""); setLoading(false);
  }

  return <SessionContext.Provider value={{ user: identity?.user, identity,
    expiresAt: identity?.expires_at, loading, error, recovering,
    restore, login, logout }}>
    {children}
  </SessionContext.Provider>;
}

export const useSession = () => useContext(SessionContext);
