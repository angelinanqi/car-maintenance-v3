"use client";

import NextLink from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { useSession } from "./SessionProvider";
import { Stack, Box, Text, Button, Flex } from "@chakra-ui/react";
import Brand from "./Brand";

const groups = [
  {
    label: "Your Work",
    items: [
      ["Home", "/admin/home"],
      ["Questions to Clarify", "/admin/review-questions"],
      ["Vehicles", "/admin/vehicles"],
      ["Reference Library", "/admin/kb"],
    ],
  },
  {
    label: "Help Drivers Learn",
    items: [
      ["Learning Guides", "/admin/learn-cards"],
      ["Learning Topics", "/admin/learn-cards/manage-cat"],
      ["Emergency Information", "/admin/emergency"],
    ],
  },
  {
    label: "Check Your Changes",
    items: [["Try the Chatbot", "/admin/chatbot"]],
  },
  {
    label: "Other Tools",
    items: [
      ["Service Task Library", "/admin/maintenance-items"],
      ["Topics & Videos", "/admin/scopes"],
      ["Account Security", "/admin/account-security"],
    ],
  },
];

export default function NavBar() {
  const pathname = usePathname();
  const session = useSession();
  const [error, setError] = useState("");
  const [open, setOpen] = useState(false);
  const [signingOut, setSigningOut] = useState(false);
  return (
    <Box
      as="nav"
      aria-label="Main navigation"
      w={{ base: "100%", lg: "248px" }}
      h={{ base: "auto", lg: "100dvh" }}
      position={{ lg: "sticky" }}
      top={0}
      px={4}
      py={5}
      bg="rail"
      color="white"
      display="flex"
      flexDirection="column"
      overflowY="auto"
      flexShrink={0}
    >
      <Flex
        justify="space-between"
        align="center"
        px={1}
        mb={{ base: 0, lg: 8 }}
      >
        <NextLink href="/admin/home" aria-label="Roadie Admin overview">
          <Brand inverse />
        </NextLink>
        <Button
          display={{ lg: "none" }}
          variant="plain"
          color="white"
          aria-expanded={open}
          aria-controls="admin-navigation"
          onClick={() => setOpen(!open)}
        >
          {open ? "Close Menu" : "Menu"}
        </Button>
      </Flex>
      <Stack
        id="admin-navigation"
        display={{ base: open ? "flex" : "none", lg: "flex" }}
        gap={5}
        mt={{ base: 5, lg: 0 }}
      >
        {groups.map((group) => (
          <Box key={group.label}>
            <Text color="#ffe08a" fontSize="sm" px={3} mb={2}>
              {group.label}
            </Text>
            <Stack gap={1}>
              {group.items.map(([label, href]) => {
                const active =
                  pathname === href ||
                  (["/admin/kb", "/admin/vehicles"].includes(href) &&
                    pathname.startsWith(`${href}/`)) ||
                  (href === "/admin/vehicles" &&
                    pathname === "/admin/schedules") ||
                  (href === "/admin/learn-cards" &&
                    pathname.startsWith("/admin/learn-cards/create"));
                return (
                  <Button
                    key={href}
                    asChild
                    variant="plain"
                    justifyContent="start"
                    fontWeight={active ? "650" : "400"}
                    bg={active ? "brand.400" : "transparent"}
                    color={active ? "ink" : "#fff8e6"}
                    _hover={{ bg: active ? "brand.300" : "#493b16" }}
                    px={3}
                    minH="42px"
                  >
                    <NextLink
                      href={href}
                      aria-current={active ? "page" : undefined}
                      onClick={() => setOpen(false)}
                    >
                      {label}
                    </NextLink>
                  </Button>
                );
              })}
            </Stack>
          </Box>
        ))}
      </Stack>
      <Box
        display={{ base: open ? "block" : "none", lg: "block" }}
        mt="auto"
        pt={7}
        px={2}
      >
        <Text fontSize="sm" fontWeight="600">
          {session.user?.display_name || "Administrator"}
        </Text>
        <Text fontSize="sm" color="#ffe08a" overflowWrap="anywhere" mt={1}>
          {session.user?.email}
        </Text>
        {error && (
          <Text role="alert" mt={3}>
            {error}
          </Text>
        )}
        <Button
          mt={3}
          size="sm"
          variant="plain"
          color="#fff8e6"
          px={0}
          loading={signingOut}
          onClick={async () => {
            setSigningOut(true);
            try {
              await session.logout();
            } catch (cause) {
              setError(cause.message);
            } finally {
              setSigningOut(false);
            }
          }}
        >
          Sign Out
        </Button>
      </Box>
    </Box>
  );
}
