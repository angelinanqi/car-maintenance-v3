"use client";

import { useEffect, useState } from "react";
import { Button, Flex, Text } from "@chakra-ui/react";

const PAGE_SIZE = 10;

export function usePagination<T>(items: T[], resetKey = "") {
  const [requestedPage, setPage] = useState(1);
  useEffect(() => { setPage(1); }, [resetKey]);
  const pageCount = Math.max(1, Math.ceil(items.length / PAGE_SIZE));
  const page = Math.min(requestedPage, pageCount);
  useEffect(() => { setPage((current) => Math.min(current, pageCount)); }, [pageCount]);
  return {
    items: items.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE),
    page, pageCount, total: items.length, onPageChange: setPage,
  };
}

export default function Pagination({ page, pageCount, total, onPageChange, label = "Results" }: {
  page: number; pageCount: number; total: number;
  onPageChange: (page: number) => void; label?: string;
}) {
  if (!total) return null;
  return <Flex as="nav" aria-label={`${label} Pagination`} gap={3} justify="space-between" align="center" wrap="wrap" py={3}>
    <Text fontSize="sm" color="muted" aria-live="polite">
      Showing {(page - 1) * PAGE_SIZE + 1}–{Math.min(page * PAGE_SIZE, total)} of {total}
    </Text>
    {pageCount > 1 && <Flex gap={3} align="center" wrap="wrap">
      <Button size="sm" variant="outline" disabled={page === 1} onClick={() => onPageChange(page - 1)}>Previous</Button>
      <Text fontSize="sm">Page {page} of {pageCount}</Text>
      <Button size="sm" variant="outline" disabled={page === pageCount} onClick={() => onPageChange(page + 1)}>Next</Button>
    </Flex>}
  </Flex>;
}
