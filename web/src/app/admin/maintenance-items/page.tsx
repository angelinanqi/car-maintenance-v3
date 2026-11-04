"use client";
import Pagination, { usePagination } from "@/components/admin/Pagination";

import { useEffect, useState } from "react";
import NextLink from "next/link";
import {
  Badge,
  Box,
  Button,
  Flex,
  Heading,
  Input,
  Stack,
  Text,
} from "@chakra-ui/react";
import AdminLayout from "@/components/layouts/AdminLayout";
import ListFilters from "@/components/admin/ListFilters";
import FormField from "@/components/admin/FormField";
import { AdminSelect } from "@/components/admin/NativeControls";
import MaintenanceItemEditor from "@/components/admin/MaintenanceItemEditor";
import ServiceTaskIntervals, { useMaintenanceIntervals } from "@/components/admin/ServiceTaskIntervals";
import { loadItems, type MaintenanceItem } from "@/api/admin";
import { useContent } from "@/components/ContentProvider";

const actionLabels = {
  inspect: "Inspect",
  replace: "Replace",
  service: "Service",
};

export default function MaintenanceItemsPage() {
  const {
    cards: guides,
    error: contentError,
    loading: contentLoading,
  } = useContent();
  const [items, setItems] = useState<MaintenanceItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [loaded, setLoaded] = useState(false);
  const [editor, setEditor] = useState<{ row?: MaintenanceItem } | null>(null);
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("");
  const [action, setAction] = useState("");
  const [status, setStatus] = useState("all");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const intervals = useMaintenanceIntervals();
  const [vehicleId, setVehicleId] = useState("");
  useEffect(() => {
    let active = true;
    loadItems()
      .then((rows) => {
        if (active) {
          setItems(rows);
          setLoaded(true);
        }
      })
      .catch((cause: Error) => {
        if (active) setError(cause.message);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);
  async function reload() {
    if (loading) return;
    setLoading(true);
    setError("");
    intervals.reload();
    try {
      setItems(await loadItems());
      setLoaded(true);
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setLoading(false);
    }
  }
  const categories = [
    ...new Set(items.map((row) => row.category).filter(Boolean)),
  ].sort();
  const visible = items
    .filter(
      (row) =>
        (!category ||
          (category === "__uncategorized"
            ? !row.category
            : row.category === category)) &&
        (!action || row.action === action) &&
        (status === "all" || row.active === (status === "active")) &&
        `${row.title} ${row.description} ${row.category}`
          .toLowerCase()
          .includes(query.trim().toLowerCase()),
    )
    .sort((a, b) => a.title.localeCompare(b.title));
  function saved(row: MaintenanceItem) {
    setItems((previous) => [
      ...previous.filter((item) => item.id !== row.id),
      row,
    ]);
    setEditor(null);
    setNotice(`${row.title} saved.`);
    setQuery("");
    setCategory("");
    setAction("");
    setStatus("all");
  }
  const pagination = usePagination(visible, JSON.stringify([query, category, action, status]));
  return (
    <AdminLayout
      title="Service Task Library"
      description="Manage service tasks and see their maintenance intervals by vehicle. Published intervals are available to drivers; drafts and unset intervals need review against the vehicle’s manual."
    >
      <Stack gap={5}>
        {notice && <Text role="status">{notice}</Text>}
        {intervals.error && <Box role="alert">
          <Text>Vehicle intervals could not be loaded: {intervals.error}</Text>
          <Button variant="outline" mt={2} onClick={intervals.reload}>Retry intervals</Button>
        </Box>}
        <FormField label="Show maintenance intervals for" hint="Intervals can differ by model year and equipment. Choose a vehicle to check its schedule.">
          <AdminSelect value={vehicleId} disabled={intervals.loading} onChange={(event) => setVehicleId(event.target.value)}>
            <option value="">All vehicles</option>
            {intervals.vehicles.map((vehicle) => <option key={vehicle.id} value={vehicle.id}>
              {[vehicle.name, vehicle.year, vehicle.variant].filter(Boolean).join(" · ")}
            </option>)}
          </AdminSelect>
        </FormField>
        {error && (
          <Box role="alert">
            <Text>{error}</Text>
            <Button
              variant="outline"
              mt={3}
              onClick={reload}
              disabled={loading}
            >
              Retry items
            </Button>
          </Box>
        )}
        <Flex gap={4} justify="space-between" align="center" wrap="wrap">
          <Text color="muted">
            {loaded
              ? `${items.filter((row) => row.active).length} active · ${items.filter((row) => !row.active).length} inactive`
              : "Loading your item library…"}
          </Text>
          <Flex gap={2} wrap="wrap">
            <Button variant="outline" loading={loading} onClick={reload}>
              Refresh
            </Button>
            <Button disabled={!loaded || loading} onClick={() => setEditor({})}>
              Add service task
            </Button>
          </Flex>
        </Flex>
        <ListFilters
          columns="2fr 1fr"
          wideColumns="2fr 1fr 1fr 1fr"
          activeCount={
            Number(Boolean(category)) +
            Number(Boolean(action)) +
            Number(status !== "all")
          }
          search={
            <FormField label="Search items">
              <Input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Name, description or category"
                disabled={!loaded}
              />
            </FormField>
          }
        >
          <FormField label="Category">
            <AdminSelect
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              disabled={!loaded}
            >
              <option value="">All categories</option>
              <option value="__uncategorized">Uncategorized</option>
              {categories.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </AdminSelect>
          </FormField>
          <FormField label="Action">
            <AdminSelect
              value={action}
              onChange={(e) => setAction(e.target.value)}
              disabled={!loaded}
            >
              <option value="">All actions</option>
              <option value="inspect">Inspect</option>
              <option value="replace">Replace</option>
              <option value="service">Service</option>
            </AdminSelect>
          </FormField>
          <FormField label="Status">
            <AdminSelect
              value={status}
              onChange={(e) => setStatus(e.target.value)}
              disabled={!loaded}
            >
              <option value="all">All items</option>
              <option value="active">Active</option>
              <option value="inactive">Inactive</option>
            </AdminSelect>
          </FormField>
        </ListFilters>
        {loaded && (
          <Text fontSize="sm" color="muted">
            Showing {visible.length} of {items.length} items. Inspection and
            replacement of the same part should be separate items.
          </Text>
        )}
        <Stack as="ul" gap={3} m={0} p={0} listStyleType="none">
          {pagination.items.map((row) => {
            const related = guides.filter(
              (guide: { maintenance_item_ids?: string[] }) =>
                guide.maintenance_item_ids?.includes(row.id),
            );
            return (
              <Box as="li" key={row.id} bg="white" borderRadius="10px" p={5}>
                <Flex gap={4} justify="space-between" align="start">
                  <Box minW={0} flex={1}>
                    <Heading as="h2" size="md">
                      {row.title}
                    </Heading>
                    <Flex gap={2} align="center" wrap="wrap" mt={2}>
                      <Badge colorPalette="brand">
                        {actionLabels[row.action]}
                      </Badge>
                      <Badge colorPalette={row.active ? "green" : "gray"}>
                        {row.active ? "Active" : "Inactive"}
                      </Badge>
                      <Text color="muted" fontSize="sm">
                        {row.category || "Uncategorized"}
                      </Text>
                    </Flex>
                    {row.description && (
                      <Text mt={3} maxW="80ch">
                        {row.description}
                      </Text>
                    )}
                  </Box>
                  <Button
                    variant="outline"
                    size="sm"
                    aria-label={`Edit ${row.title}`}
                    onClick={() => setEditor({ row })}
                  >
                    Edit
                  </Button>
                </Flex>
                <ServiceTaskIntervals itemId={row.id} schedules={intervals.schedules} vehicles={intervals.vehicles}
                  vehicleId={vehicleId} loading={intervals.loading} error={intervals.error} />
                <Box bg="canvas" px={3} py={2} borderRadius="6px" mt={4}>
                  <Text fontSize="sm" fontWeight="600">
                    Related learning guides
                  </Text>
                  {related.length ? (
                    <Flex gap={3} wrap="wrap" mt={1}>
                      {related.map(
                        (guide: {
                          id: string;
                          title: string;
                          status: string;
                        }) => (
                          <NextLink
                            key={guide.id}
                            href={`/admin/learn-cards/create?edit=${guide.id}`}
                            style={{
                              textDecoration: "underline",
                              fontSize: 14,
                            }}
                          >
                            {guide.title} ({guide.status})
                          </NextLink>
                        ),
                      )}
                    </Flex>
                  ) : (
                    <Text fontSize="sm" color="muted">
                      {contentLoading
                        ? "Loading guide relationships?"
                        : contentError
                          ? "Guide relationships could not be confirmed. Retry loading the workspace above."
                          : "No linked guides. Add this item under related maintenance items when editing a learning guide."}
                    </Text>
                  )}
                </Box>
              </Box>
            );
          })}
        </Stack>
        {loaded && !visible.length && (
          <Box bg="white" p={8} borderRadius="10px">
            <Heading as="h2" size="md">
              {items.length
                ? "No Matching Items"
                : "Start Your Maintenance Library"}
            </Heading>
            <Text mt={2} color="muted">
              {items.length
                ? "Try different filters or clear them to see every item."
                : "Add one reusable operation at a time. Schedules will refer to these items by their name and action."}
            </Text>
            {items.length > 0 && (
              <Button
                mt={4}
                variant="outline"
                onClick={() => {
                  setQuery("");
                  setCategory("");
                  setAction("");
                  setStatus("all");
                }}
              >
                Clear filters
              </Button>
            )}
          </Box>
        )}
        <Pagination {...pagination} label="Service Tasks" />
        <Flex
          bg="brand.100"
          p={5}
          borderRadius="10px"
          justify="space-between"
          gap={4}
          wrap="wrap"
          align="center"
        >
          <Box>
            <Text fontWeight="600">Need to set a service interval?</Text>
            <Text fontSize="sm" mt={1}>
              Choose a vehicle in Service schedules, then add these items with
              reviewed distance or time rules.
            </Text>
          </Box>
          <Button asChild variant="outline">
            <NextLink href="/admin/schedules">Open service schedules</NextLink>
          </Button>
        </Flex>
      </Stack>
      {editor && (
        <MaintenanceItemEditor
          row={editor.row}
          categories={categories}
          onClose={() => setEditor(null)}
          onSaved={saved}
        />
      )}
    </AdminLayout>
  );
}
