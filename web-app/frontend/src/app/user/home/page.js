import { Grid, Card, Text, Box, Heading, Stack } from '@chakra-ui/react';
import AdminLayout from '../../../components/layouts/AdminLayout';

export default function Home() {
    // =========================================================================
    // BACKEND INTEGRATION EXAMPLE:
    // To connect real data, fetch it via server components, React Query, or useEffect.
    //
    // Example:
    // const [stats, setStats] = useState({ totalRevenue: 0, totalUsers: 0 });
    // useEffect(() => {
    //    fetch('/api/stats').then(res => res.json()).then(data => setStats(data));
    // }, []);
    // =========================================================================

    const totalRevenue = "$45,231.89"; // Replace with variable: stats.totalRevenue
    const activeUsers = "+2,350";      // Replace with variable: stats.activeUsers
    const totalOrders = "12,234";      // Replace with variable: stats.totalOrders
    const pendingTasks = "12";         // Replace with variable: stats.pendingTasks

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
                                        Total Revenue
                                    </Text>
                                    <Heading size="xl" mt={1}>
                                        {/* CONNECT VARIABLE HERE: {totalRevenue} */}
                                        {totalRevenue}
                                    </Heading>
                                </Box>
                                {/* Top-Right Description / Badge */}
                                <Text fontSize="xs" color="green.600" fontWeight="bold">
                                    +20.1% vs last mo
                                </Text>
                            </Grid>
                        </Card.Body>
                    </Card.Root>

                    {/* Stat Card 2 */}
                    <Card.Root variant="outline">
                        <Card.Body p={4}>
                            <Grid templateColumns="1fr auto" alignItems="start" gap={2}>
                                <Box>
                                    <Text fontSize="xs" color="gray.500" fontWeight="medium">
                                        Active Users
                                    </Text>
                                    <Heading size="xl" mt={1}>
                                        {/* CONNECT VARIABLE HERE: {activeUsers} */}
                                        {activeUsers}
                                    </Heading>
                                </Box>
                                <Text fontSize="xs" color="gray.500">
                                    Active now
                                </Text>
                            </Grid>
                        </Card.Body>
                    </Card.Root>

                    {/* Stat Card 3 */}
                    <Card.Root variant="outline">
                        <Card.Body p={4}>
                            <Grid templateColumns="1fr auto" alignItems="start" gap={2}>
                                <Box>
                                    <Text fontSize="xs" color="gray.500" fontWeight="medium">
                                        Total Orders
                                    </Text>
                                    <Heading size="xl" mt={1}>
                                        {/* CONNECT VARIABLE HERE: {totalOrders} */}
                                        {totalOrders}
                                    </Heading>
                                </Box>
                                <Text fontSize="xs" color="green.600" fontWeight="bold">
                                    +12% this week
                                </Text>
                            </Grid>
                        </Card.Body>
                    </Card.Root>

                    {/* Stat Card 4 */}
                    <Card.Root variant="outline">
                        <Card.Body p={4}>
                            <Grid templateColumns="1fr auto" alignItems="start" gap={2}>
                                <Box>
                                    <Text fontSize="xs" color="gray.500" fontWeight="medium">
                                        Pending Tasks
                                    </Text>
                                    <Heading size="xl" mt={1}>
                                        {/* CONNECT VARIABLE HERE: {pendingTasks} */}
                                        {pendingTasks}
                                    </Heading>
                                </Box>
                                <Text fontSize="xs" color="red.500">
                                    3 High priority
                                </Text>
                            </Grid>
                        </Card.Body>
                    </Card.Root>

                </Grid>

                {/* BOTTOM SECTION: 2 Large Content Cards */}
                <Grid templateColumns={{ base: '1fr', lg: '2fr 1fr' }} gap={6}>

                    {/* Bottom Card 1 (e.g., Chart / Main Data) */}
                    <Card.Root variant="outline" minH="300px">
                        <Card.Header pb={2}>
                            <Heading size="md">Main Analytics / Chart Space</Heading>
                            <Text fontSize="sm" color="gray.500">
                                Placeholder description for your main feature/graph
                            </Text>
                        </Card.Header>
                        <Card.Body>
                            <Text color="gray.400">
                                [ Content goes here later - e.g., Recharts line graph or table ]
                            </Text>
                        </Card.Body>
                    </Card.Root>

                    {/* Bottom Card 2 (e.g., Recent Activity / Side Panel) */}
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