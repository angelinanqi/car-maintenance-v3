import { Flex, Box, Heading, Text, VStack } from '@chakra-ui/react';
import NavBar from '../NavBar'; // Your previously built component

export default function AdminLayout({ title, description, children }) {
    return (
        // Outer Container: Locks layout to 100vh
        <Flex h="100vh" w="100vw" overflow="hidden">

            {/* 1. Left Sidebar */}
            <Box w="250px" flexShrink={0} h="100%">
                <NavBar />
            </Box>

            {/* 2. Main Scrollable Content Area */}
            <Flex
                direction="column"
                flex={1}
                h="100%"
                overflowY="auto"
            >
                {/* Content Wrapper: Aligned left, capped width */}
                <Box
                    w="100%"
                    maxW="1200px"
                    /* Removed mx="auto" so it doesn't float into the center when zooming out */
                    pt="30px"
                    px="30px"
                    pb="30px"
                >
                    {/* Header Area */}
                    <VStack align="start" gap={1} mb={6}>
                        <Heading as="h1" size="lg">
                            {title}
                        </Heading>
                        {description && (
                            <Text color="gray.600" fontSize="sm">
                                {description}
                            </Text>
                        )}
                    </VStack>

                    {/* Dynamic Inner Page Content */}
                    <Box as="main">
                        {children}
                    </Box>
                </Box>
            </Flex>

        </Flex>
    );
}