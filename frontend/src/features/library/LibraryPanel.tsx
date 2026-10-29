import React, { Suspense, lazy, useEffect, useMemo, useRef, useState } from "react";
import { BookOpen, PanelLeftClose, Plus, Search } from "lucide-react";
import { createCollection, fetchCollections } from "../../api/client";
import type { Page } from "../../api/types";
import { AddLinkInput } from "./AddLinkInput";
import { LibraryPageRow } from "./LibraryPageRow";
import { strings } from "../../strings";

const VirtualPageList = lazy(() =>
  import("./VirtualPageList").then((module) => ({ default: module.VirtualPageList })),
);

type PageFilter = "all" | "indexed" | "working" | "failed";

interface LibraryPanelProps {
  pages: Page[];
  selectedScopeIds: string[];
  onToggleScope: (doc_id: string) => void;
  onToggleCollectionScope: (doc_ids: string[]) => void;
  onClearScope: () => void;
  onPageAdded: (page: Page) => void;
  onOpenSource: (doc_id: string) => void;
  onRefetch: (doc_id: string) => Promise<void>;
  onRemove: (doc_id: string) => Promise<void>;
  selectedCollection: string;
  onSelectCollection: (col: string) => void;
  onCollapseRail: () => void;
}

export const LibraryPanel: React.FC<LibraryPanelProps> = ({
  pages,
  selectedScopeIds,
  onToggleScope,
  onToggleCollectionScope,
  onClearScope,
  onPageAdded,
  onOpenSource,
  onRefetch,
  onRemove,
  selectedCollection,
  onSelectCollection,
  onCollapseRail,
}) => {
  const [searchQuery, setSearchQuery] = useState("");
  const [pageFilter, setPageFilter] = useState<PageFilter>("all");
  const [highlightedPageId, setHighlightedPageId] = useState<string | null>(null);
  const [collectionNames, setCollectionNames] = useState<string[]>(["default"]);
  const [collectionsError, setCollectionsError] = useState("");
  const [showCreateCollection, setShowCreateCollection] = useState(false);
  const [newCollectionName, setNewCollectionName] = useState("");
  const [creatingCollection, setCreatingCollection] = useState(false);
  const [createCollectionError, setCreateCollectionError] = useState("");
  const [collectionNotice, setCollectionNotice] = useState("");
  const pageListRef = useRef<HTMLDivElement>(null);
  const highlightTimerRef = useRef<number | null>(null);

  useEffect(() => {
    let active = true;
    fetchCollections()
      .then((names) => {
        if (active) {
          setCollectionNames(names);
          setCollectionsError("");
        }
      })
      .catch((error: unknown) => {
        if (active) {
          const message = error instanceof Error ? error.message : strings.ariaLibrary;
          setCollectionsError(strings.loadCollectionsError(message));
        }
      });

    return () => {
      active = false;
    };
  }, []);

  const collections = useMemo(
    () =>
      Array.from(
        new Set([
          "default",
          ...collectionNames,
          ...pages.map((page) => page.collection).filter(Boolean),
        ]),
      ).sort((left, right) => left.localeCompare(right)),
    [collectionNames, pages],
  );
  const collectionPages = useMemo(
    () => pages.filter((page) => page.collection === selectedCollection),
    [pages, selectedCollection],
  );
  const selectedCollectionPageCount = collectionPages.filter((page) =>
    selectedScopeIds.includes(page.doc_id),
  ).length;
  const allCollectionPagesSelected =
    collectionPages.length > 0 &&
    selectedCollectionPageCount === collectionPages.length;
  const hasFailedPages = collectionPages.some((page) => page.status === "failed");
  const filteredPages = useMemo(() => {
    const query = searchQuery.trim().toLocaleLowerCase();
    return collectionPages.filter((page) => {
      if (pageFilter === "indexed" && page.status !== "ready") return false;
      if (
        pageFilter === "working" &&
        (page.status === "ready" || page.status === "failed")
      ) {
        return false;
      }
      if (pageFilter === "failed" && page.status !== "failed") return false;
      if (!query) return true;

      return (
        page.title.toLocaleLowerCase().includes(query) ||
        page.domain.toLocaleLowerCase().includes(query)
      );
    });
  }, [collectionPages, pageFilter, searchQuery]);

  useEffect(
    () => () => {
      if (highlightTimerRef.current !== null) {
        window.clearTimeout(highlightTimerRef.current);
      }
    },
    [],
  );

  const handleDuplicatePage = (page: Page) => {
    setSearchQuery("");
    setPageFilter("all");
    onSelectCollection(page.collection);
    setHighlightedPageId(page.doc_id);
    if (highlightTimerRef.current !== null) {
      window.clearTimeout(highlightTimerRef.current);
    }
    highlightTimerRef.current = window.setTimeout(() => {
      setHighlightedPageId(null);
      highlightTimerRef.current = null;
    }, 3000);
  };

  const handleCreateCollection = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setCreateCollectionError("");
    setCollectionNotice("");
    setCreatingCollection(true);

    try {
      const createdName = await createCollection(newCollectionName);
      setCollectionNames((names) =>
        Array.from(new Set([...names, createdName])).sort((left, right) =>
          left.localeCompare(right),
        ),
      );
      onSelectCollection(createdName);
      setNewCollectionName("");
      setShowCreateCollection(false);
      setCollectionNotice(strings.collectionCreated(createdName));
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : strings.createCollection;
      setCreateCollectionError(strings.createCollectionError(message));
    } finally {
      setCreatingCollection(false);
    }
  };

  const renderPageRow = (page: Page) => (
    <LibraryPageRow
      key={page.doc_id}
      page={page}
      isSelectedForScope={selectedScopeIds.includes(page.doc_id)}
      isHighlighted={highlightedPageId === page.doc_id}
      onToggleScope={onToggleScope}
      onOpenSource={onOpenSource}
      onRefetch={onRefetch}
      onRemove={onRemove}
    />
  );

  return (
    <aside
      aria-label={strings.ariaLibrary}
      className="flex h-full min-h-0 flex-col border-r border-line bg-rail"
    >
      <header className="flex items-center justify-between border-b border-line px-3 py-3">
        <div className="flex min-w-0 items-center gap-2">
          <BookOpen className="h-4 w-4 shrink-0 text-accent" aria-hidden="true" />
          <h2 className="text-sm font-semibold text-text">{strings.ariaLibrary}</h2>
          <span className="rounded bg-surface-2 px-1.5 py-0.5 text-xs tabular-nums text-text-muted">
            {pages.length}
          </span>
        </div>
        <button
          type="button"
          onClick={onCollapseRail}
          className="flex min-h-9 min-w-9 items-center justify-center rounded text-text-muted hover:bg-surface-2 hover:text-text"
          title={strings.titleCollapseLibrary}
          aria-label={strings.titleCollapseLibrary}
        >
          <PanelLeftClose className="h-4 w-4" aria-hidden="true" />
        </button>
      </header>

      <div className="space-y-3 border-b border-line p-3">
        <div className="space-y-1">
          <div className="flex items-center justify-between gap-2">
            <label htmlFor="library-collection" className="text-xs font-medium text-text-muted">
              {strings.collectionLabel}
            </label>
            <button
              type="button"
              onClick={() => {
                setShowCreateCollection((visible) => !visible);
                setCreateCollectionError("");
              }}
              aria-expanded={showCreateCollection}
              className="inline-flex min-h-8 items-center gap-1 rounded px-2 text-xs font-medium text-accent hover:bg-accent-soft"
            >
              <Plus className="h-3.5 w-3.5" aria-hidden="true" />
              {strings.createCollection}
            </button>
          </div>
          <select
            id="library-collection"
            value={selectedCollection}
            onChange={(event) => onSelectCollection(event.target.value)}
            className="min-h-10 w-full rounded-ctrl border border-line bg-surface px-3 text-sm text-text focus-visible:border-accent"
            aria-label={strings.selectCollection}
          >
            {collections.map((collection) => (
              <option key={collection} value={collection}>
                {collection}
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={() =>
              onToggleCollectionScope(
                collectionPages.map((page) => page.doc_id),
              )
            }
            disabled={collectionPages.length === 0}
            className="min-h-8 w-full rounded px-2 text-left text-xs font-medium text-accent hover:bg-accent-soft disabled:cursor-not-allowed disabled:text-text-muted"
          >
            {allCollectionPagesSelected
              ? strings.clearCollectionScope
              : strings.selectAllCollectionPages(collectionPages.length)}
          </button>
        </div>
        {showCreateCollection && (
          <form onSubmit={(event) => void handleCreateCollection(event)} className="space-y-1.5">
            <label className="sr-only" htmlFor="new-collection-name">
              {strings.collectionNamePlaceholder}
            </label>
            <div className="flex gap-2">
              <input
                id="new-collection-name"
                value={newCollectionName}
                onChange={(event) => {
                  setNewCollectionName(event.target.value);
                  setCreateCollectionError("");
                }}
                maxLength={63}
                disabled={creatingCollection}
                placeholder={strings.collectionNamePlaceholder}
                aria-describedby={createCollectionError ? "create-collection-error" : "collection-name-hint"}
                className="min-h-10 min-w-0 flex-1 rounded-ctrl border border-line bg-surface px-3 text-sm text-text placeholder:text-text-muted focus-visible:border-accent disabled:opacity-60"
              />
              <button
                type="submit"
                disabled={creatingCollection || !newCollectionName.trim()}
                className="inline-flex min-h-10 shrink-0 items-center justify-center rounded-ctrl bg-accent px-3 text-sm font-medium text-accent-fg hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {creatingCollection ? strings.creatingCollection : strings.createCollection}
              </button>
            </div>
            <p id="collection-name-hint" className="text-xs text-text-muted">
              {strings.collectionNameHint}
            </p>
            {createCollectionError && (
              <p id="create-collection-error" role="alert" className="text-xs text-err">
                {createCollectionError}
              </p>
            )}
          </form>
        )}
        {collectionsError && (
          <p role="alert" className="text-xs text-err">{collectionsError}</p>
        )}
        {collectionNotice && (
          <p role="status" className="text-xs text-ok">{collectionNotice}</p>
        )}
        <AddLinkInput
          onPageAdded={onPageAdded}
          onDuplicatePage={handleDuplicatePage}
          selectedCollection={selectedCollection}
        />
      </div>

      {pages.length > 0 && (
        <div className="space-y-2 border-b border-line p-3">
          <label className="relative block" htmlFor="library-search">
            <Search
              className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-muted"
              aria-hidden="true"
            />
            <input
              id="library-search"
              type="search"
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
              placeholder={strings.searchSavedPages}
              className="min-h-10 w-full rounded-ctrl border border-line bg-surface py-2 pl-9 pr-3 text-sm text-text placeholder:text-text-muted focus-visible:border-accent"
            />
          </label>
          {hasFailedPages && (
            <div className="flex flex-wrap gap-1" role="group" aria-label={strings.filterPages}>
              {(
                [
                  ["all", strings.statusAll],
                  ["indexed", strings.statusIndexed],
                  ["working", strings.statusWorking],
                  ["failed", strings.statusFailed],
                ] as const
              ).map(([filter, label]) => (
                <button
                  key={filter}
                  type="button"
                  onClick={() => setPageFilter(filter)}
                  aria-pressed={pageFilter === filter}
                  className={`min-h-8 rounded-ctrl border px-2 text-xs ${
                    pageFilter === filter
                      ? "border-accent bg-accent-soft font-medium text-accent"
                      : "border-transparent text-text-muted hover:bg-surface hover:text-text"
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      <div
        ref={pageListRef}
        className="min-h-0 flex-1 overflow-y-auto p-2"
        aria-label={strings.savedPages}
      >
        {pages.length === 0 ? (
          <p className="p-3 text-sm leading-6 text-text-muted">{strings.addFirstPage}</p>
        ) : filteredPages.length === 0 ? (
          <p className="p-3 text-sm text-text-muted">{strings.noMatchingPages}</p>
        ) : filteredPages.length > 100 ? (
          <Suspense fallback={<p className="p-3 text-sm text-text-muted">{strings.loadingPageList}</p>}>
            <VirtualPageList
              pages={filteredPages}
              scrollElementRef={pageListRef}
              highlightedPageId={highlightedPageId}
              renderPageRow={renderPageRow}
            />
          </Suspense>
        ) : (
          <div className="space-y-1">{filteredPages.map(renderPageRow)}</div>
        )}
      </div>

      {selectedScopeIds.length > 0 && (
        <footer className="sticky bottom-0 flex shrink-0 items-center justify-between gap-2 border-t border-line bg-surface px-3 py-2">
          <span className="min-w-0 truncate text-sm font-medium text-text">
            {strings.scopeSelectedCount(selectedScopeIds.length)}
          </span>
          <button
            type="button"
            onClick={onClearScope}
            className="min-h-9 shrink-0 rounded px-2 text-sm text-accent hover:bg-accent-soft"
          >
            {strings.clearScope}
          </button>
        </footer>
      )}
    </aside>
  );
};
