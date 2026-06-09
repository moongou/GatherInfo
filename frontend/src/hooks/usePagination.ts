import { useState, useMemo } from "react";

interface UsePaginationOptions {
  totalItems: number;
  pageSize?: number;
  initialPage?: number;
}

interface UsePaginationReturn {
  page: number;
  totalPages: number;
  setPage: (p: number) => void;
  offset: number;
  hasNext: boolean;
  hasPrev: boolean;
}

export function usePagination({
  totalItems,
  pageSize = 40,
  initialPage = 1,
}: UsePaginationOptions): UsePaginationReturn {
  const [page, setPage] = useState(initialPage);
  const totalPages = Math.max(1, Math.ceil(totalItems / pageSize));
  const offset = (page - 1) * pageSize;

  return {
    page,
    totalPages,
    setPage: (p) => setPage(Math.max(1, Math.min(p, totalPages))),
    offset,
    hasNext: page < totalPages,
    hasPrev: page > 1,
  };
}
