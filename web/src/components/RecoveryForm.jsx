"use client";

import { useEffect, useState } from "react";
import NextLink from "next/link";
import { Box, Button, Field, Flex, Heading, Input, Stack, Text } from "@chakra-ui/react";
import { browserAuth, authRedirect, authResult, authError, passwordError } from "@/lib/supabase.mjs";
import { useSession } from "./SessionProvider";
import { PasswordInput } from "./ui/password-input";
import Brand from "./Brand";

export default function RecoveryForm({ mode }) {
  const session = useSession();
  const reset = mode === "reset";
  const resend = mode === "resend";
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [retryAt, setRetryAt] = useState(0);
  const [seconds, setSeconds] = useState(0);
  useEffect(() => {
    try { setRetryAt(Number(sessionStorage.getItem("roadie-email-retry-at")) || 0); } catch { /* Use the page cooldown if storage is blocked. */ }
  }, []);
  useEffect(() => {
    const tick = () => setSeconds(Math.max(0, Math.ceil((retryAt - Date.now()) / 1000)));
    tick();
    const timer = setInterval(tick, 1000);
    return () => clearInterval(timer);
  }, [retryAt]);
  function cooldown() {
    const deadline = Date.now() + 60000;
    setRetryAt(deadline);
    try { sessionStorage.setItem("roadie-email-retry-at", String(deadline)); } catch { /* Page state still prevents repeated clicks. */ }
  }
  async function submit(event) {
    event.preventDefault();
    if (busy || !event.currentTarget.reportValidity()) return;
    setError(""); setMessage("");
    if (reset && (passwordError(password) || password !== confirm)) {
      setError(passwordError(password) || "Passwords must match."); return;
    }
    if (reset && !session.recovering) { setError("Open a valid recovery email in this browser first."); return; }
    if (!reset && seconds > 0) return;
    setBusy(true);
    try {
      const auth = browserAuth();
      if (reset) {
        await authResult(auth.updateUser({ password }));
        setMessage("Your password was updated. Finishing sign-out.");
        try { await session.logout(); }
        catch { throw new Error("Your password was updated, but sign-out could not be confirmed. Retry signing out before continuing."); }
        setPassword(""); setConfirm("");
        setMessage("Password updated. Sign in with your new password.");
      } else {
        if (resend) await authResult(auth.resend({ type: "signup", email: email.trim(), options: { emailRedirectTo: authRedirect() } }));
        else await authResult(auth.resetPasswordForEmail(email.trim(), { redirectTo: authRedirect() }));
        setMessage("If this account can receive the requested email, check its inbox. Open the latest link in this browser.");
        cooldown();
      }
    } catch (cause) {
      setError(authError(cause));
      if (cause.status === 429 || ["over_email_send_rate_limit", "over_request_rate_limit"].includes(cause.code)) cooldown();
    } finally { setBusy(false); }
  }
  return <Flex minH="100dvh" align="center" justify="center" p={5}>
    <Stack bg="white" p={{ base: 6, md: 10 }} borderRadius="12px" maxW="480px" w="full" gap={5}>
      <Brand /><Heading size="lg">{reset ? "Choose a New Password" : resend ? "Confirm Your Email" : "Reset Your Password"}</Heading>
      <Text>{reset ? "Use 8–20 characters." : "Enter your account email. Open the latest link in this browser."}</Text>
      {session.loading && reset ? <Text role="status">Checking your recovery session…</Text> :
        reset && !session.recovering && !message ? <Text role="alert">Open a valid recovery email first. Request a new link if the previous one expired.</Text> :
        <Box as="form" onSubmit={submit}><Stack gap={5}>
          {reset ? <>
            <Field.Root><Field.Label htmlFor="new-password">New password</Field.Label>
              <PasswordInput id="new-password" value={password} onChange={event => setPassword(event.target.value)} required minLength={8} maxLength={20} autoComplete="new-password" disabled={busy} />
            </Field.Root>
            <Field.Root><Field.Label htmlFor="confirm-password">Confirm new password</Field.Label>
              <PasswordInput id="confirm-password" value={confirm} onChange={event => setConfirm(event.target.value)} required maxLength={20} autoComplete="new-password" disabled={busy} />
            </Field.Root>
          </> : <Field.Root><Field.Label htmlFor="recovery-email">Email address</Field.Label>
            <Input id="recovery-email" type="email" value={email} onChange={event => setEmail(event.target.value)} required autoComplete="email" disabled={busy} />
          </Field.Root>}
          <Button type="submit" loading={busy} disabled={(!reset && seconds > 0) || (reset && !session.recovering)}>
            {reset ? "Update password" : seconds > 0 ? `Try again in ${seconds}s` : "Send email"}
          </Button>
        </Stack></Box>}
      {error && <Text role="alert">{error}</Text>}
      {message && <Text role="status">{message}</Text>}
      <NextLink href="/login">Back to sign in</NextLink>
      {reset && <NextLink href="/forgot-password">Request a new recovery link</NextLink>}
    </Stack>
  </Flex>;
}
