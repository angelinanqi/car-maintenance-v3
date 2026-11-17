"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import NextLink from "next/link";
import { Flex, Stack, Text } from "@chakra-ui/react";
import { useSession } from "@/components/SessionProvider";

export default function Page() {
  const session = useSession();
  const router = useRouter();
  const [partialEmailConfirmation, setPartialEmailConfirmation] = useState(null);
  useEffect(() => {
    const url = new URL(window.location.href);
    const message = url.searchParams.get("message") || new URLSearchParams(url.hash.slice(1)).get("message");
    setPartialEmailConfirmation(message?.startsWith("Confirmation link accepted.") ?? false);
  }, []);
  useEffect(() => {
    if (partialEmailConfirmation === false && !session.loading && session.user) {
      router.replace(session.recovering ? "/reset-password" : "/admin/home");
    }
  }, [partialEmailConfirmation, session.loading, session.user, session.recovering, router]);
  if (partialEmailConfirmation) return <Flex minH="100dvh" align="center" justify="center" p={6}>
    <Stack gap={5}>
      <Text role="status">One address confirmed. Open the link sent to the other email address to finish changing your email.</Text>
      <NextLink href="/admin/account-security">Back to account settings</NextLink>
    </Stack>
  </Flex>;
  return <Flex minH="100dvh" align="center" justify="center" p={6}><Stack gap={5}>
    <Text role={session.error ? "alert" : "status"}>{session.error || (session.loading || session.user ? "Verifying your account link…" : "This link could not establish a session. Request a new link and open it in the browser where you requested it.")}</Text>
    <NextLink href="/login">Sign in</NextLink><NextLink href="/forgot-password">Request recovery email</NextLink>
    <NextLink href="/resend-confirmation">Resend confirmation</NextLink>
  </Stack></Flex>;
}
