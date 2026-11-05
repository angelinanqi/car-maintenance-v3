"use client";

import { useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import { Box, Button, Stack, Text, Flex } from "@chakra-ui/react";
import NavBar from "@/components/NavBar";
import Brand from "@/components/Brand";
import { useSession } from "@/components/SessionProvider";
import { ContentProvider } from "@/components/ContentProvider";
import AdminMfa from "@/components/AdminMfa";

export default function AdminWorkspaceLayout({ children }) {
  const session = useSession();
  const router = useRouter();
  const pathname = usePathname();
  useEffect(() => {
    if (session.recovering) { router.replace("/reset-password"); return; }
    if (!session.loading && !session.error && !session.user) router.replace("/login");
  }, [session.loading, session.error, session.user, session.recovering, router]);
  if (session.recovering) return <AccessState><Text role="status">Opening password recovery…</Text></AccessState>;
  if (session.loading) return <AccessState><Text role="status">Restoring your session…</Text></AccessState>;
  if (session.error) return <AccessState><Text role="alert">{session.error}</Text><Button onClick={session.restore}>Retry connection</Button><Button onClick={() => router.replace("/login")}>Go to sign in</Button></AccessState>;
  if (!session.user) return <AccessState><Text role="status">Opening sign in…</Text></AccessState>;
  if (session.user.role !== "admin") return <AccessState><Text fontWeight="600" fontSize="xl">Administrator access required</Text><Text color="muted">Your account works in MyRoadie. Ask your administrator to assign access before using this workspace.</Text><Button onClick={session.restore}>Refresh access</Button><Button onClick={async () => { try { await session.logout(); } catch { await session.restore(); } }}>Sign out</Button></AccessState>;
  if (!session.identity?.access_allowed) return <AdminMfa key={session.user.id} />;
  return <ContentProvider key={session.user.id} emergencyOnly={pathname === "/admin/emergency"}>
    <Box as="a" href="#main-content" position="fixed" top="-100px" left={4} zIndex={2000} bg="brand.400" color="ink" px={4} py={3} _focus={{ top: 4 }}>Skip to content</Box>
    <Flex minH="100dvh" direction={{ base: "column", lg: "row" }}>
      <NavBar />
      <Box as="main" id="main-content" tabIndex={-1} flex={1} minW={0}>{children}</Box>
    </Flex>
  </ContentProvider>;
}

function AccessState({ children }) {
  return <Flex minH="100dvh" align="center" justify="center" p={5}><Stack bg="white" p={{ base: 6, md: 10 }} borderRadius="12px" maxW="480px" w="full" gap={5}><Brand />{children}</Stack></Flex>;
}
