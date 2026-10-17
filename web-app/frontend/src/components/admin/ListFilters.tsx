"use client";

import { useId, useState, type ReactNode } from "react";
import { Box, Button, Grid } from "@chakra-ui/react";

export default function ListFilters({
  search,
  children,
  columns,
  wideColumns,
  activeCount = 0,
}: {
  search: ReactNode;
  children: ReactNode;
  columns: string;
  wideColumns?: string;
  activeCount?: number;
}) {
  const [expanded, setExpanded] = useState(false);
  const id = useId();
  return (
    <Grid
      templateColumns={{ base: "1fr", md: columns, xl: wideColumns || columns }}
      gap={4}
      alignItems="end"
    >
      {search}
      <Button
        display={{ base: "inline-flex", md: "none" }}
        justifySelf="start"
        variant="outline"
        aria-expanded={expanded}
        aria-controls={id}
        onClick={() => setExpanded(!expanded)}
      >
        {expanded ? "Hide filters" : "Filters"}
        {activeCount ? ` (${activeCount})` : ""}
      </Button>
      <Box
        id={id}
        role="group"
        aria-label="List filters"
        display={{ base: expanded ? "contents" : "none", md: "contents" }}
      >
        {children}
      </Box>
    </Grid>
  );
}
