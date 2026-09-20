import NextLink from 'next/link';
import { VStack, Box, Text, Button, Separator } from '@chakra-ui/react';

export default function NavBar() {
    const navItems = [
        { label: 'Home', href: '/user/home' },
        { label: 'Knowledge Base', href: '/user/kb' },
        { label: 'Learn Cards', href: '/user/learn-cards' },
        { label: 'Emergency', href: '/user/emergency' },
    ];

    return (
        <Box
            as="nav"
            w="240px"
            h="100vh"
            p={4}
            borderRight="1px solid"
            borderColor="gray.200"
        >
            <VStack align="stretch" gap={4}>
                <Box px={2} py={2}>
                    <Text fontSize="xl" fontWeight="bold" letterSpacing="tight">
                        Car App
                    </Text>
                </Box>

                <Separator />

                <VStack align="stretch" gap={1}>
                    {navItems.map((item) => (
                        <Button
                            key={item.label}
                            asChild
                            variant="ghost"
                            justifyContent="flex-start"
                            w="100%"
                            fontWeight="normal"
                        >
                            <NextLink href={item.href}>
                                {item.label}
                            </NextLink>
                        </Button>
                    ))}
                </VStack>
            </VStack>
        </Box>
    );
}