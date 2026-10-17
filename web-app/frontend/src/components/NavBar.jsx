"use client";

import NextLink from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { useSession } from "./SessionProvider";
import { Stack, Box, Text, Button, Flex } from "@chakra-ui/react";
import Brand from "./Brand";

const groups = [
  { label: "Workspace", items: [["Overview", "/user/home"]] },
  { label: "Vehicle care", items: [["Vehicle catalogue", "/user/vehicles"], ["Maintenance items", "/user/maintenance-items"], ["Service schedules", "/user/schedules"]] },
  { label: "Knowledge & content", items: [["Documents", "/user/kb"], ["Knowledge scopes", "/user/scopes"], ["Learning guides", "/user/learn-cards"], ["Learning categories", "/user/learn-cards/manage-cat"], ["Emergency & contacts", "/user/emergency"]] },
  { label: "Quality assurance", items: [["Chat preview", "/user/chatbot"]] },
];

export default function NavBar() {
  const pathname = usePathname();
  const session = useSession();
  const [error, setError] = useState("");
  const [open, setOpen] = useState(false);
  const [signingOut, setSigningOut] = useState(false);
  return (
    <Box as="nav" aria-label="Main navigation" w={{ base: "100%", lg: "248px" }} h={{ base: "auto", lg: "100dvh" }} position={{ lg: "sticky" }} top={0} px={4} py={5} bg="rail" color="white" display="flex" flexDirection="column" overflowY="auto" flexShrink={0}>
      <Flex justify="space-between" align="center" px={1} mb={{ base: 0, lg: 8 }}>
        <NextLink href="/user/home" aria-label="Roadie Admin overview"><Brand inverse /></NextLink>
        <Button display={{ lg: "none" }} variant="plain" color="white" aria-expanded={open} aria-controls="admin-navigation" onClick={() => setOpen(!open)}>{open ? "Close menu" : "Menu"}</Button>
      </Flex>
      <Stack id="admin-navigation" display={{ base: open ? "flex" : "none", lg: "flex" }} gap={5} mt={{ base: 5, lg: 0 }}>
        {groups.map((group) => <Box key={group.label}>
          <Text color="#abb7c4" fontSize="sm" px={3} mb={2}>{group.label}</Text>
          <Stack gap={1}>{group.items.map(([label, href]) => {
            const active = pathname === href || (href === "/user/learn-cards" && pathname.startsWith("/user/learn-cards/create"));
            return <Button key={href} asChild variant="plain" justifyContent="start" fontWeight={active ? "650" : "400"} bg={active ? "brand.400" : "transparent"} color={active ? "ink" : "#e2e7ed"} _hover={{ bg: active ? "brand.300" : "#303d49" }} px={3} minH="42px">
              <NextLink href={href} aria-current={active ? "page" : undefined} onClick={() => setOpen(false)}>{label}</NextLink>
            </Button>;
          })}</Stack>
        </Box>)}
      </Stack>
      <Box display={{ base: open ? "block" : "none", lg: "block" }} mt="auto" pt={7} px={2}>
        <Text fontSize="sm" fontWeight="600">{session.user?.display_name || "Administrator"}</Text>
        <Text fontSize="sm" color="#abb7c4" overflowWrap="anywhere" mt={1}>{session.user?.email}</Text>
        {error && <Text role="alert" mt={3}>{error}</Text>}
        <Button mt={3} size="sm" variant="plain" color="#e2e7ed" px={0} loading={signingOut} onClick={async () => {
          setSigningOut(true);
          try { await session.logout(); } catch (cause) { setError(cause.message); }
          finally { setSigningOut(false); }
        }}>Sign out</Button>
      </Box>
    </Box>
  );
}
