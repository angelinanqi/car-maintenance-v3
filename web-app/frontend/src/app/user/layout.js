"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { Box, Button, Stack, Text } from "@chakra-ui/react";
import { useSession } from "@/components/SessionProvider";
import { ContentProvider } from "@/components/ContentProvider";

export default function UserLayout({ children }) {
  const session = useSession();
  const router = useRouter();
  useEffect(() => {
    if (!session.loading && !session.error && !session.user) router.replace("/login");
  }, [session.loading, session.error, session.user, router]);
  if (session.loading) return <Box p={8}>Restoring your session...</Box>;
  if (session.error) return <Stack p={8}><Text role="alert">{session.error}</Text><Button onClick={session.restore}>Retry</Button></Stack>;
  if (!session.user) return <Box p={8}>Opening login...</Box>;
  if (session.user.role !== "admin") return <Stack p={8}><Text>Administrator access is required. This account can be used in the mobile app.</Text><Button onClick={async () => { try { await session.logout(); } catch { await session.restore(); } }}>Sign out</Button></Stack>;
  return <ContentProvider>{children}</ContentProvider>;
}
