import React, { useEffect, useState } from "react";
import {
  AlertCircle,
  ExternalLink,
  Loader2,
  RefreshCw,
  Trash2,
  X,
} from "lucide-react";
import type { Page, PageStatus } from "../../api/types";
import { cleanDisplayTitle } from "../../lib/text";
import { strings } from "../../strings";

interface LibraryPageRowProps {
  page: Page;
  isSelectedForScope: boolean;
  isHighlighted?: boolean;
  onToggleScope: (doc_id: string) => void;
  onOpenSource: (doc_id: string) => void;
  onRefetch: (doc_id: string) => Promise<void>;
  onRemove: (doc_id: string) => Promise<void>;
}

function statusLabel(status: PageStatus): string | null {
  switch (status) {
    case "queued":
      return strings.pageStatusQueued;
    case "fetching":
      return strings.pageStatusFetching;
    case "extracting":
      return strings.pageStatusExtracting;
    case "indexing":
      return strings.pageStatusIndexing;
    case "failed":
      return strings.pageStatusFailed;
    case "ready":
      return null;
  }
}

function formatTimeAgo(dateString: string, now: number | null): string {
  if (!dateString || now === null) return "";
  const timestamp = new Date(dateString).getTime();
  if (!Number.isFinite(timestamp)) return "";

  const elapsedSeconds = Math.max(0, Math.floor((now - timestamp) / 1000));
  if (elapsedSeconds < 60) return strings.justNow;
  if (elapsedSeconds < 3600) return strings.minutesAgo(Math.floor(elapsedSeconds / 60));
  if (elapsedSeconds < 86400) return strings.hoursAgo(Math.floor(elapsedSeconds / 3600));
  return strings.daysAgo(Math.floor(elapsedSeconds / 86400));
}

export const LibraryPageRow: React.FC<LibraryPageRowProps> = ({
  page,
  isSelectedForScope,
  isHighlighted = false,
  onToggleScope,
  onOpenSource,
  onRefetch,
  onRemove,
}) => {
  const [now, setNow] = useState<number | null>(null);
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [expandedError, setExpandedError] = useState(false);
  const [busyAction, setBusyAction] = useState<"retry" | "delete" | null>(null);
  const [actionError, setActionError] = useState("");

  useEffect(() => {
    const timerId = window.setTimeout(() => setNow(Date.now()), 0);
    return () => window.clearTimeout(timerId);
  }, []);

  const displayTitle = cleanDisplayTitle(page.title) || page.domain;
  const statusText = statusLabel(page.status);
  const isWorking = page.status !== "ready" && page.status !== "failed";
  const fetchedTime = formatTimeAgo(page.fetched_at, now);

  const handleRetry = async () => {
    setBusyAction("retry");
    setActionError("");
    try {
      await onRefetch(page.doc_id);
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : strings.pageStatusFailed;
      setActionError(strings.pageRetryFailed(message));
    } finally {
      setBusyAction(null);
    }
  };

  const handleDelete = async () => {
    setBusyAction("delete");
    setActionError("");
    try {
      await onRemove(page.doc_id);
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : strings.pageStatusFailed;
      setActionError(strings.deletePageFailed(message));
      setBusyAction(null);
    }
  };

  return (
    <article
      className={`rounded-ctrl border px-2.5 py-2 transition-colors ${
        isHighlighted
          ? "border-accent bg-accent-soft"
          : "border-transparent hover:border-line hover:bg-surface"
      }`}
      data-page-id={page.doc_id}
    >
      <div className="flex min-w-0 items-start gap-2">
        <input
          type="checkbox"
          checked={isSelectedForScope}
          onChange={() => onToggleScope(page.doc_id)}
          className="mt-0.5 h-6 w-6 shrink-0 accent-accent focus-visible:outline"
          aria-label={strings.selectedPageScope(displayTitle)}
        />
        <div className="min-w-0 flex-1">
          <button
            type="button"
            onClick={() => onOpenSource(page.doc_id)}
            className="block min-h-6 w-full truncate text-left text-sm font-medium text-text hover:text-accent"
            title={displayTitle}
          >
            {displayTitle}
          </button>
          <p className="mt-0.5 flex min-w-0 items-center gap-1.5 truncate text-xs text-text-muted">
            <span className="truncate">{page.domain}</span>
            <span aria-hidden="true">·</span>
            <span className="shrink-0">{strings.pagePassageCount(page.chunk_count)}</span>
            {fetchedTime && (
              <>
                <span aria-hidden="true">·</span>
                <span className="shrink-0">{fetchedTime}</span>
              </>
            )}
          </p>
        </div>
        {statusText && (
          <span
            className={`inline-flex min-h-6 shrink-0 items-center gap-1 rounded border px-1.5 text-xs ${
              page.status === "failed"
                ? "border-err/40 text-err"
                : "border-line text-text-muted"
            }`}
            aria-label={isWorking ? strings.pageWorkingOn(statusText.toLowerCase()) : statusText}
          >
            {isWorking && <Loader2 className="h-3 w-3 animate-spin" aria-hidden="true" />}
            {page.status === "failed" && (
              <AlertCircle className="h-3 w-3" aria-hidden="true" />
            )}
            {statusText}
          </span>
        )}
      </div>

      {isWorking && (
        <div
          className="ml-6 mt-2 h-0.5 overflow-hidden rounded bg-line"
          role="progressbar"
          aria-label={strings.pageWorkingOn(statusText?.toLowerCase() ?? "")}
        >
          <div className="h-full w-1/3 animate-pulse rounded bg-accent" />
        </div>
      )}

      {page.status === "failed" && (
        <div className="ml-6 mt-1 flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => void handleRetry()}
            disabled={busyAction !== null}
            className="inline-flex min-h-8 items-center gap-1 rounded px-2 text-xs font-medium text-accent hover:bg-accent-soft disabled:opacity-60"
          >
            {busyAction === "retry" ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
            ) : (
              <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
            )}
            {strings.pageRetry}
          </button>
          {page.error && (
            <button
              type="button"
              onClick={() => setExpandedError((expanded) => !expanded)}
              aria-expanded={expandedError}
              className="min-h-8 rounded px-2 text-xs text-text-muted hover:bg-surface-2 hover:text-text"
            >
              {expandedError ? strings.close : strings.failedPageDetails}
            </button>
          )}
        </div>
      )}

      {expandedError && page.error && (
        <p className="ml-6 mt-1 break-words text-xs text-err" role="status">
          {page.error}
        </p>
      )}
      {actionError && (
        <p className="ml-6 mt-1 break-words text-xs text-err" role="alert">
          {actionError}
        </p>
      )}

      <div className="ml-6 mt-1 flex flex-wrap items-center gap-1">
        <a
          href={page.canonical_url}
          target="_blank"
          rel="noreferrer"
          className="inline-flex min-h-8 items-center gap-1 rounded px-2 text-xs text-text-muted hover:bg-surface-2 hover:text-text"
          aria-label={strings.openOriginalPage}
        >
          <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
          {strings.openPage}
        </a>
        {page.status === "ready" && (
          <button
            type="button"
            onClick={() => void handleRetry()}
            disabled={busyAction !== null}
            className="inline-flex min-h-8 items-center gap-1 rounded px-2 text-xs text-text-muted hover:bg-surface-2 hover:text-text disabled:opacity-60"
            aria-label={strings.refetchPage}
          >
            {busyAction === "retry" ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
            ) : (
              <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
            )}
            {strings.refetchPage}
          </button>
        )}
        {!confirmingDelete ? (
          <button
            type="button"
            onClick={() => setConfirmingDelete(true)}
            disabled={busyAction !== null}
            className="inline-flex min-h-8 items-center gap-1 rounded px-2 text-xs text-text-muted hover:bg-err/10 hover:text-err disabled:opacity-60"
            aria-label={strings.deletePage}
          >
            <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
            {strings.deletePage}
          </button>
        ) : (
          <>
            <button
              type="button"
              onClick={() => void handleDelete()}
              disabled={busyAction !== null}
              className="inline-flex min-h-8 items-center gap-1 rounded bg-err px-2 text-xs font-medium text-white disabled:opacity-60"
            >
              {busyAction === "delete" ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
              ) : (
                <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
              )}
              {busyAction === "delete" ? strings.deletingPage : strings.confirmDeletePage}
            </button>
            <button
              type="button"
              onClick={() => setConfirmingDelete(false)}
              disabled={busyAction !== null}
              className="inline-flex min-h-8 items-center gap-1 rounded px-2 text-xs text-text-muted hover:bg-surface-2 disabled:opacity-60"
            >
              <X className="h-3.5 w-3.5" aria-hidden="true" />
              {strings.cancel}
            </button>
          </>
        )}
      </div>
    </article>
  );
};
