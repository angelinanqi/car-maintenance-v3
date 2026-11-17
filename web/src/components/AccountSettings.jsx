"use client";

import { useEffect, useState } from "react";
import {
  Box, Button, Dialog, Field, Flex, Heading, Input, Portal, Stack, Text,
} from "@chakra-ui/react";
import { accountSessions, deleteAccount, revokeAccountSession, updateDisplayName } from "@/api/accounts.mjs";
import { authError, authRedirect, authResult, browserAuth, passwordError } from "@/lib/supabase.mjs";
import { useSession } from "./SessionProvider";
import AdminMfa from "./AdminMfa";
import { PasswordInput } from "./ui/password-input";

function SettingsCard({ title, action, children }) {
  return (
    <Stack as="section" bg="white" borderWidth="1px" borderRadius="lg" p={{ base: 5, md: 6 }} gap={4}>
      <Flex align="center" justify="space-between" gap={3}>
        <Heading as="h2" size="md">{title}</Heading>
        {action}
      </Flex>
      {children}
    </Stack>
  );
}

function Feedback({ error, message }) {
  return <>
    {error && <Text color="red.700" role="alert">{error}</Text>}
    {message && <Text role="status">{message}</Text>}
  </>;
}

function ProfileSettings({ user, restore }) {
  const [name, setName] = useState(null);
  const [newEmail, setNewEmail] = useState("");
  const [editingEmail, setEditingEmail] = useState(false);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const displayName = (name ?? user.display_name).trim();

  async function save(event, field) {
    event.preventDefault();
    if (busy) return;
    setBusy(field);
    setError("");
    setMessage("");
    try {
      if (field === "name") {
        await updateDisplayName(displayName);
        const refreshed = await restore();
        if (refreshed?.user.display_name === displayName) setName(null);
        setMessage("Name updated.");
      } else {
        await authResult(browserAuth().updateUser({ email: newEmail.trim() }, { emailRedirectTo: authRedirect() }));
        setMessage("Check your current and new inboxes for confirmation links. Open any links you receive in this browser.");
        setEditingEmail(false);
        setNewEmail("");
      }
    } catch (cause) {
      setError(authError(cause));
    } finally {
      setBusy("");
    }
  }

  return <SettingsCard title="Profile">
    <Box as="form" onSubmit={event => save(event, "name")}>
      <Stack align="start" gap={3}>
        <Field.Root>
          <Field.Label htmlFor="profile-name">Display name</Field.Label>
          <Input id="profile-name" value={name ?? user.display_name} onChange={event => setName(event.target.value)}
            autoComplete="name" maxLength={100} required disabled={Boolean(busy)} />
        </Field.Root>
        <Button size="sm" type="submit" loading={busy === "name"}
          disabled={Boolean(busy) || !displayName || displayName === user.display_name}>Save name</Button>
      </Stack>
    </Box>
    <Box borderTopWidth="1px" pt={4}>
      <Text fontWeight="semibold">Email address</Text>
      <Text color="muted" overflowWrap="anywhere">{user.email}</Text>
      {editingEmail ? (
        <Box as="form" mt={3} onSubmit={event => save(event, "email")}>
          <Stack gap={3}>
            <Field.Root>
              <Field.Label htmlFor="new-email">New email address</Field.Label>
              <Input id="new-email" type="email" autoComplete="email" value={newEmail}
                onChange={event => setNewEmail(event.target.value)} required disabled={Boolean(busy)} />
            </Field.Root>
            <Flex gap={2} wrap="wrap">
              <Button size="sm" type="submit" loading={busy === "email"} disabled={Boolean(busy) ||
                !newEmail.trim() || newEmail.trim().toLowerCase() === user.email.toLowerCase()}>Send confirmation</Button>
              <Button size="sm" variant="ghost" disabled={Boolean(busy)} onClick={() => {
                setEditingEmail(false);
                setNewEmail("");
              }}>Cancel</Button>
            </Flex>
          </Stack>
        </Box>
      ) : <Button mt={3} size="sm" variant="outline" disabled={Boolean(busy)} onClick={() => {
        setError("");
        setMessage("");
        setEditingEmail(true);
      }}>Change email</Button>}
    </Box>
    <Feedback error={error} message={message} />
  </SettingsCard>;
}

function PasswordSettings({ onChanged }) {
  const [current, setCurrent] = useState("");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [needsCode, setNeedsCode] = useState(false);
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  async function update(operation) {
    if (busy) return;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await operation();
    } catch (cause) {
      if (cause.code === "reauthentication_needed") {
        setNeedsCode(true);
        setError("Request a verification code to continue.");
      } else {
        setError(authError(cause));
      }
    } finally {
      setBusy(false);
    }
  }

  function submit(event) {
    event.preventDefault();
    const invalid = passwordError(password) || (password !== confirmation && "Passwords must match.");
    if (invalid) { setError(invalid); return; }
    update(async () => {
      await authResult(browserAuth().updateUser({
        current_password: current, password, ...(needsCode && { nonce: code.trim() }),
      }));
      setCurrent("");
      setPassword("");
      setConfirmation("");
      setCode("");
      setNeedsCode(false);
      setMessage("Password updated.");
      onChanged();
    });
  }

  return <SettingsCard title="Change password">
    <Box as="form" onSubmit={submit}>
      <Stack gap={4} align="start">
        <Field.Root>
          <Field.Label htmlFor="current-password">Current password</Field.Label>
          <PasswordInput id="current-password" autoComplete="current-password" value={current}
            onChange={event => setCurrent(event.target.value)} required disabled={busy} />
        </Field.Root>
        <Field.Root>
          <Field.Label htmlFor="change-password">New password</Field.Label>
          <PasswordInput id="change-password" autoComplete="new-password" value={password}
            onChange={event => setPassword(event.target.value)} required disabled={busy} />
          <Field.HelperText>Use 8 to 20 characters.</Field.HelperText>
        </Field.Root>
        <Field.Root>
          <Field.Label htmlFor="confirm-change-password">Confirm new password</Field.Label>
          <PasswordInput id="confirm-change-password" autoComplete="new-password" value={confirmation}
            onChange={event => setConfirmation(event.target.value)} required disabled={busy} />
        </Field.Root>
        {needsCode && <>
          <Button variant="outline" size="sm" disabled={busy} onClick={() => update(async () => {
            await authResult(browserAuth().reauthenticate());
            setMessage("Check your email for a verification code.");
          })}>Send verification code</Button>
          <Field.Root>
            <Field.Label htmlFor="password-code">Email verification code</Field.Label>
            <Input id="password-code" value={code} onChange={event => setCode(event.target.value)}
              autoComplete="one-time-code" inputMode="numeric" pattern="[0-9]{6}" required disabled={busy} />
          </Field.Root>
        </>}
        <Button size="sm" type="submit" loading={busy}>Update password</Button>
      </Stack>
    </Box>
    <Feedback error={error} message={message} />
  </SettingsCard>;
}

function SessionSettings({ revision, refresh }) {
  const [sessions, setSessions] = useState(null);
  const [loadError, setLoadError] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    accountSessions(controller.signal).then(rows => {
      if (!controller.signal.aborted) {
        setSessions(rows);
        setLoadError("");
      }
    }).catch(cause => { if (!controller.signal.aborted) setLoadError(cause.message); });
    return () => controller.abort();
  }, [revision]);

  async function revoke({ id, device }) {
    if (busy || !window.confirm(`Sign out of this ${device} session?`)) return;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await revokeAccountSession(id);
      setSessions(rows => rows?.filter(row => row.id !== id));
      setMessage("Session signed out.");
    } catch (cause) {
      setError(cause.message);
      refresh();
    } finally {
      setBusy(false);
    }
  }

  return <SettingsCard title="Signed-in sessions" action={
    <Button size="xs" variant="outline" onClick={refresh} disabled={busy}>Refresh</Button>
  }>
    {loadError && <Text role="alert">{loadError}</Text>}
    {!sessions && !loadError && <Text role="status">Loading sessions…</Text>}
    {sessions?.length === 0 && <Text>No sessions to display. Refresh to check again.</Text>}
    {sessions?.map(row => (
      <Flex key={row.id} borderTopWidth="1px" pt={3} gap={3} align="center" justify="space-between" wrap="wrap">
        <Box>
          <Text fontWeight="semibold">{row.device}{row.current ? " (this session)" : ""}</Text>
          <Text fontSize="sm" color="muted">Last active {new Date(row.last_active_at).toLocaleString()}</Text>
        </Box>
        {!row.current && <Button size="sm" variant="outline" disabled={busy} onClick={() => revoke(row)}>Sign out</Button>}
      </Flex>
    ))}
    <Feedback error={error} message={message} />
  </SettingsCard>;
}

function DeleteSettings({ session }) {
  const factors = session.identity.factor_ids;
  const [selected, setSelected] = useState("");
  const [open, setOpen] = useState(false);
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [deleted, setDeleted] = useState(false);
  const [error, setError] = useState("");

  async function remove(event) {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      if (!deleted) {
        await authResult(browserAuth().mfa.challengeAndVerify({ factorId: selected || factors[0], code: code.trim() }));
        await deleteAccount();
        setDeleted(true);
        setCode("");
      }
      await session.logout();
    } catch (cause) {
      setError(authError(cause));
    } finally {
      setBusy(false);
    }
  }

  return <SettingsCard title="Delete account">
    <Text color="muted">Permanently delete your MyRoadie account and the personal records saved to it.</Text>
    <Dialog.Root role="alertdialog" open={open} onOpenChange={({ open: next }) => {
      if (busy) return;
      setOpen(next);
      setCode("");
      setError("");
    }}>
      <Dialog.Trigger asChild>
        <Button size="sm" colorPalette="red" variant="outline" alignSelf="start">Delete account</Button>
      </Dialog.Trigger>
      <Portal>
        <Dialog.Backdrop />
        <Dialog.Positioner>
          <Dialog.Content mx={4}>
            <Box as="form" onSubmit={remove}>
              <Dialog.Header><Dialog.Title>Delete your account?</Dialog.Title></Dialog.Header>
              <Dialog.Body>
                <Stack gap={4}>
                  <Text>{deleted ? "Your account was deleted. Sign out to finish." :
                    "Your account, vehicles, service records, chats, and saved items will be removed. This cannot be undone."}</Text>
                  {!deleted && <>
                    {factors.length > 1 && <Field.Root>
                      <Field.Label htmlFor="delete-factor">Authenticator</Field.Label>
                      <Box as="select" id="delete-factor" value={selected || factors[0]} disabled={busy}
                        onChange={event => setSelected(event.target.value)} borderWidth="1px" p={2}>
                        {factors.map((id, index) => <option key={id} value={id}>Authenticator {index + 1}</option>)}
                      </Box>
                    </Field.Root>}
                    <Field.Root>
                      <Field.Label htmlFor="delete-code">6-digit authenticator code</Field.Label>
                      <Input id="delete-code" value={code} onChange={event => setCode(event.target.value)}
                        autoComplete="one-time-code" inputMode="numeric" pattern="[0-9]{6}" required disabled={busy} />
                    </Field.Root>
                  </>}
                  <Feedback error={error} />
                </Stack>
              </Dialog.Body>
              <Dialog.Footer>
                <Dialog.ActionTrigger asChild><Button variant="outline" disabled={busy}>Cancel</Button></Dialog.ActionTrigger>
                <Button type="submit" colorPalette="red" loading={busy}>{deleted ? "Sign out" : "Delete account"}</Button>
              </Dialog.Footer>
            </Box>
          </Dialog.Content>
        </Dialog.Positioner>
      </Portal>
    </Dialog.Root>
  </SettingsCard>;
}

export default function AccountSettings() {
  const session = useSession();
  const [revision, setRevision] = useState(0);
  const refresh = () => setRevision(value => value + 1);
  return <Stack maxW="680px" mx="auto" p={{ base: 4, md: 8 }} gap={5}>
    <Heading as="h1" size="2xl">Account settings</Heading>
    <ProfileSettings key={session.user.id} user={session.user} restore={session.restore} />
    <PasswordSettings key={`password-${session.user.id}`} onChanged={refresh} />
    <AdminMfa manage />
    <SessionSettings key={`sessions-${session.user.id}`} revision={revision} refresh={refresh} />
    <DeleteSettings key={`delete-${session.user.id}`} session={session} />
  </Stack>;
}
