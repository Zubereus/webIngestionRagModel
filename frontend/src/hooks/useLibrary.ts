import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import type { Page } from "../api/types";
import {
  fetchBackendHealth,
  fetchPages,
  isMockMode,
  subscribePageEvents,
} from "../api/client";

const PAGES_QUERY_KEY = ["pages"];
const HEALTH_QUERY_KEY = ["backend-health"];

function hasPendingPages(pages: Page[] | undefined): boolean {
  return Boolean(
    pages?.some((page) => page.status !== "ready" && page.status !== "failed"),
  );
}

export function useLibrary() {
  const queryClient = useQueryClient();
  const [eventsConnected, setEventsConnected] = useState(false);
  const mockMode = isMockMode();

  const healthQuery = useQuery({
    queryKey: HEALTH_QUERY_KEY,
    queryFn: fetchBackendHealth,
    refetchInterval: 5000,
    retry: false,
  });

  const pagesQuery = useQuery({
    queryKey: PAGES_QUERY_KEY,
    queryFn: () => fetchPages(),
    refetchInterval: (query) =>
      !eventsConnected && hasPendingPages(query.state.data) ? 3000 : false,
    retry: false,
  });

  useEffect(() => {
    if (mockMode) return;

    const closeEvents = subscribePageEvents({
      onConnectionChange: setEventsConnected,
      onPageEvent: () => {
        void queryClient.invalidateQueries({ queryKey: PAGES_QUERY_KEY });
      },
    });

    return closeEvents;
  }, [mockMode, queryClient]);

  const refresh = async () => {
    await Promise.all([
      healthQuery.refetch(),
      pagesQuery.refetch(),
    ]);
  };

  const addPage = (page: Page) => {
    queryClient.setQueryData<Page[]>(PAGES_QUERY_KEY, (pages = []) => [
      page,
      ...pages.filter((existingPage) => existingPage.doc_id !== page.doc_id),
    ]);
  };

  const removePage = (docId: string) => {
    queryClient.setQueryData<Page[]>(PAGES_QUERY_KEY, (pages = []) =>
      pages.filter((page) => page.doc_id !== docId),
    );
  };

  const clearPages = () => {
    queryClient.setQueryData<Page[]>(PAGES_QUERY_KEY, []);
  };

  return {
    pages: pagesQuery.data ?? [],
    pagesError: pagesQuery.error,
    backendOnline: isMockMode() || healthQuery.data !== null,
    modelName: healthQuery.data?.model ?? null,
    refresh,
    addPage,
    removePage,
    clearPages,
  };
}
