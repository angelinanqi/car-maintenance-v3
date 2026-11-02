"use client";

import { useState } from "react";
import { Box, Button, Field, Flex, Heading, Input, Stack, Text } from "@chakra-ui/react";
import { browserAuth, authResult, authError } from "@/lib/supabase.mjs";
import { useSession } from "./SessionProvider";
import Brand from "./Brand";

export default function AdminMfa({ manage = false }) {
  const session = useSession();
  const factors = session.identity?.factor_ids || [];
  const [enrollment, setEnrollment] = useState(null);
  const [selected, setSelected] = useState("");
  const [verified, setVerified] = useState("");
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  async function enroll() {
    if (busy) return;
    setBusy(true); setError(""); setMessage("");
    try {
      const auth = browserAuth();
      const listed = await authResult(auth.mfa.listFactors());
      for (const factor of listed.all.filter(item => item.status === "unverified")) {
        await authResult(auth.mfa.unenroll({ factorId: factor.id }));
      }
      setEnrollment(await authResult(auth.mfa.enroll({ factorType: "totp", issuer: "Roadie Admin", friendlyName: `Authenticator ${Date.now()}` })));
    } catch (cause) { setError(authError(cause)); }
    finally { setBusy(false); }
  }
  async function verify(event) {
    event.preventDefault();
    if (busy || !event.currentTarget.reportValidity()) return;
    const factorId = enrollment?.id || selected || factors[0];
    if (!factorId) return;
    setBusy(true); setError("");
    try {
      await authResult(browserAuth().mfa.challengeAndVerify({ factorId, code: code.trim() }));
      setVerified(factorId); setEnrollment(null); setCode("");
      setMessage("Authenticator verified. Keep a backup authenticator before replacing a device.");
      await session.restore();
    } catch (cause) { setError(authError(cause)); }
    finally { setBusy(false); }
  }
  async function remove() {
    const factorId = selected || factors[0];
    if (busy || factors.length < 2 || !verified || factorId === verified) return;
    if (!window.confirm("Remove this authenticator? Keep access to the authenticator you just verified.")) return;
    setBusy(true); setError("");
    try {
      await authResult(browserAuth().mfa.unenroll({ factorId }));
      await authResult(browserAuth().refreshSession());
      setSelected("");
      await session.restore();
      setMessage("Authenticator removed. MFA remains required.");
    } catch (cause) { setError(authError(cause)); }
    finally { setBusy(false); }
  }
  return <Flex minH={manage ? undefined : "100dvh"} align="center" justify="center" p={5}>
    <Stack bg="white" p={{ base: 6, md: 10 }} borderRadius="12px" maxW="520px" w="full" gap={5}>
      {!manage && <Brand />}
      <Heading size="lg">{manage ? "Account Security" : factors.length ? "Verify Your Authenticator" : "Set Up Your Authenticator"}</Heading>
      <Text>Supabase administrators must complete authenticator verification before entering the workspace.</Text>
      <Text>Keep a second authenticator as a backup. If every authenticator is lost, contact a trusted operator for identity-verified recovery.</Text>
      {!enrollment && (!factors.length || manage) && <Button onClick={enroll} loading={busy}>{factors.length ? "Add backup authenticator" : "Set up authenticator"}</Button>}
      {enrollment && <>
        <Text>Scan this code in your authenticator app, or enter the private setup key. Then verify a code.</Text>
        <Box as="img" src={enrollment.totp.qr_code} alt="Authenticator setup QR code" w="220px" h="220px" alignSelf="center" />
        <Text as="code" overflowWrap="anywhere" userSelect="all" aria-label="Authenticator setup key">{enrollment.totp.secret}</Text>
      </>}
      {(enrollment || factors.length > 0) && <Box as="form" onSubmit={verify}><Stack gap={4}>
        {!enrollment && <Field.Root><Field.Label htmlFor="auth-factor">Authenticator</Field.Label>
          <Box as="select" id="auth-factor" value={selected || factors[0]} onChange={event => setSelected(event.target.value)} disabled={busy} borderWidth="1px" p={3}>
            {factors.map((id, index) => <option key={id} value={id}>Authenticator {index + 1}</option>)}
          </Box>
        </Field.Root>}
        <Field.Root><Field.Label htmlFor="auth-code">6-digit authenticator code</Field.Label>
          <Input id="auth-code" value={code} onChange={event => setCode(event.target.value)} inputMode="numeric" pattern="[0-9]{6}" maxLength={6} autoComplete="one-time-code" required disabled={busy} />
        </Field.Root>
        <Button type="submit" loading={busy}>Verify authenticator</Button>
      </Stack></Box>}
      {manage && factors.length > 1 && verified && (selected || factors[0]) !== verified &&
        <Button variant="outline" onClick={remove} disabled={busy}>Remove selected authenticator</Button>}
      {error && <Text role="alert">{error}</Text>}
      {message && <Text role="status">{message}</Text>}
      {!manage && <Button variant="outline" disabled={busy} onClick={async () => { try { await session.logout(); } catch (cause) { setError(authError(cause)); } }}>Cancel and sign out</Button>}
    </Stack>
  </Flex>;
}
