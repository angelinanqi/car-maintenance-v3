import { Grid, Card, Text, Box, Heading, Stack } from '@chakra-ui/react';
import AdminLayout from '../../../components/layouts/AdminLayout';

export default function Home() {
    // =========================================================================
    // BACKEND INTEGRATION EXAMPLE:
    // To connect real data, fetch it via server components, React Query, or useEffect.
    // =========================================================================

    const totalDocuments = "0";
    const learningCards = "0";
    const emergencySteps = "0";

    return (
        <AdminLayout title="Home" description="Welcome back!">
            <Stack gap={6}>

                {/* TOP SECTION: 4 Stat Cards */}
                <Grid templateColumns={{ base: '1fr', md: 'repeat(2, 1fr)', xl: 'repeat(4, 1fr)' }} gap={4}>

                    {/* Stat Card 1 */}
                    <Card.Root variant="outline">
                        <Card.Body p={4}>
                            <Grid templateColumns="1fr auto" alignItems="start" gap={2}>
                                <Box>
                                    <Text fontSize="xs" color="gray.500" fontWeight="medium">
                                        Documents
                                    </Text>
                                    <Heading size="xl" mt={1}>
                                        {totalDocuments}
                                    </Heading>
                                </Box>
                            </Grid>
                        </Card.Body>
                    </Card.Root>

                    {/* Stat Card 2 */}
                    <Card.Root variant="outline">
                        <Card.Body p={4}>
                            <Grid templateColumns="1fr auto" alignItems="start" gap={2}>
                                <Box>
                                    <Text fontSize="xs" color="gray.500" fontWeight="medium">
                                        Learning Cards
                                    </Text>
                                    <Heading size="xl" mt={1}>
                                        {learningCards}
                                    </Heading>
                                </Box>
                            </Grid>
                        </Card.Body>
                    </Card.Root>

                    {/* Stat Card 3 */}
                    <Card.Root variant="outline">
                        <Card.Body p={4}>
                            <Grid templateColumns="1fr auto" alignItems="start" gap={2}>
                                <Box>
                                    <Text fontSize="xs" color="gray.500" fontWeight="medium">
                                        Emergency Steps
                                    </Text>
                                    <Heading size="xl" mt={1}>
                                        {emergencySteps}
                                    </Heading>
                                </Box>
                            </Grid>
                        </Card.Body>
                    </Card.Root>

                    {/* Stat Card 4 */}
                    <Card.Root variant="outline">
                        <Card.Body p={4}>
                            <Grid templateColumns="1fr auto" alignItems="start" gap={2}>
                                <Box>
                                    <Text fontSize="xs" color="gray.500" fontWeight="medium">
                                        Card 4
                                    </Text>
                                    <Heading size="xl" mt={1}>
                                        -
                                    </Heading>
                                </Box>
                            </Grid>
                        </Card.Body>
                    </Card.Root>

                </Grid>

                {/* BOTTOM SECTION: 2 Large Content Cards */}
                <Grid templateColumns={{ base: '1fr', lg: '2fr 1fr' }} gap={6}>

                    {/* Bottom Card 1 */}
                    <Card.Root variant="outline" minH="300px">
                        <Card.Body />
                    </Card.Root>

                    {/* Bottom Card 2 (Recent Activity) */}
                    <Card.Root variant="outline" minH="300px">
                        <Card.Header pb={2}>
                            <Heading size="md">Recent Activity</Heading>
                            <Text fontSize="sm" color="gray.500">
                                Secondary data or activity feed
                            </Text>
                        </Card.Header>
                        <Card.Body>
                            <Text color="gray.400">
                                [ Content goes here later - e.g., Recent logs or user list ]
                            </Text>
                        </Card.Body>
                    </Card.Root>

                </Grid>

            </Stack>
        </AdminLayout>
    );
}