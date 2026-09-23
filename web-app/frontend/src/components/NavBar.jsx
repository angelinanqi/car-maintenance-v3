"use client";

import NextLink from "next/link";
import { usePathname } from "next/navigation";
import { Stack, Box, Text, Button } from "@chakra-ui/react";

export default function NavBar() {
  const pathname = usePathname();
  const navItems = [
    { label: "Home", href: "/user/home" },
    { label: "Knowledge Base", href: "/user/kb" },
    { label: "Learn Cards", href: "/user/learn-cards" },
    { label: "Emergency", href: "/user/emergency" },
  ];

  return (
    <Box as="nav" aria-label="Main navigation" w={{ base: "100%", md: "240px" }}
      h={{ base: "auto", md: "100vh" }} position={{ md: "sticky" }} top={0}
      p={4} bg="white" borderRightWidth={{ md: "1px" }} borderBottomWidth={{ base: "1px", md: "0" }} borderColor="gray.200">
      <Text fontSize="xl" fontWeight="bold" px={2} mb={4}>Car App</Text>
      <Stack direction={{ base: "row", md: "column" }} gap={1} overflowX="auto">
        {navItems.map((item) => {
          const active = pathname === item.href || pathname.startsWith(item.href + "/");
          return (
            <Button key={item.href} asChild variant={active ? "subtle" : "ghost"}
              colorPalette={active ? "blue" : "gray"} justifyContent="flex-start" flexShrink={0}>
              <NextLink href={item.href} aria-current={active ? "page" : undefined}>{item.label}</NextLink>
            </Button>
          );
        })}
      </Stack>
    </Box>
  );
}
