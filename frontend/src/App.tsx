import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  BookOpen,
  Settings,
  WifiOff,
  RefreshCw,
} from "lucide-react";
import type { Page } from "./api/types";
import {
  clearLibrary,
  deletePage,
  refetchPage,
  getApiBaseUrl,
  getSelectedModel,
  isMockMode,
  setSelectedModel,
} from "./api/client";
import { LibraryPanel } from "./features/library/LibraryPanel";
import { Composer } from "./features/ask/Composer";
import { AnswerMessage } from "./features/ask/AnswerMessage";
import { SourcePanel } from "./features/source/SourcePanel";
import { SettingsDrawer } from "./components/SettingsDrawer";
import { useTheme } from "./hooks/useTheme";
import { useLibrary } from "./hooks/useLibrary";
import { useConversation } from "./hooks/useConversation";
import { strings } from "./strings";
import { suggestedQuestionsForPages } from "./lib/suggestions";
import { claimForCitation } from "./lib/trace";

export const App: React.FC = () => {
  const { theme, setTheme } = useTheme();
  const library = useLibrary();
  const conversation = useConversation();

  // Layout & UI state
  const [libraryCollapsed, setLibraryCollapsed] = useState(() => window.innerWidth < 1280);
  const [activeTabMobile, setActiveTabMobile] = useState<"ask" | "evidence" | "library">("ask");
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [selectedModel, setSelectedModelState] = useState<string | null>(
    () => getSelectedModel(),
  );
  const [activeChunkId, setActiveChunkId] = useState<string | null>(null);
  const [preview, setPreview] = useState<{ chunkId: string; claim: string } | null>(null);
  const [activeClaim, setActiveClaim] = useState("");

  // Data & Search state
  const [selectedScopeIds, setSelectedScopeIds] = useState<string[]>([]);
  const [selectedCollection, setSelectedCollection] = useState<string>("default");
  const [retrievalMode, setRetrievalMode] = useState<"hybrid" | "dense">("hybrid");
  const [topK, setTopK] = useState(5);
  const [showJumpToLatest, setShowJumpToLatest] = useState(false);
  const isNearBottomRef = useRef(true);
  const chatScrollRef = useRef<HTMLDivElement>(null);
  const { pages, pagesError, backendOnline, modelName } = library;
  const { messages, isStreaming } = conversation;
  const loadLibraryData = library.refresh;
  const handleModelChange = useCallback((model: string) => {
    setSelectedModel(model);
    setSelectedModelState(model);
  }, []);

  useEffect(() => {
    const handleResize = () => setLibraryCollapsed(window.innerWidth < 1280);
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  // Keyboard Navigation: Esc to close layers, 1-9 for citations
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        if (settingsOpen) setSettingsOpen(false);
        else if (activeChunkId || preview || activeTabMobile === "evidence") {
          setActiveChunkId(null);
          setPreview(null);
          setActiveClaim("");
          setActiveTabMobile("ask");
        }
      } else if (!e.ctrlKey && !e.metaKey && e.target === document.body) {
        if (e.key === "/") {
          e.preventDefault();
          document.querySelector<HTMLTextAreaElement>(".composer-input")?.focus();
          return;
        }
        const num = parseInt(e.key, 10);
        if (num >= 1 && num <= 9) {
          const lastMsg = [...messages].reverse().find((m) => m.role === "assistant");
          const targetCit = lastMsg?.citations?.find((c) => c.n === num);
          if (targetCit) {
            setActiveChunkId(targetCit.chunk_id);
            setActiveClaim(lastMsg ? claimForCitation(lastMsg.content, num) : "");
            setActiveTabMobile("evidence");
          }
        }
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [settingsOpen, activeChunkId, messages, preview, activeTabMobile]);

  const handleChatScroll = () => {
    const scrollContainer = chatScrollRef.current;
    if (!scrollContainer) return;
    const distanceToBottom =
      scrollContainer.scrollHeight -
      scrollContainer.scrollTop -
      scrollContainer.clientHeight;
    isNearBottomRef.current = distanceToBottom <= 80;
    if (isNearBottomRef.current) setShowJumpToLatest(false);
  };

  useEffect(() => {
    const scrollContainer = chatScrollRef.current;
    if (!scrollContainer) return;
    if (isNearBottomRef.current) {
      scrollContainer.scrollTop = scrollContainer.scrollHeight;
      setShowJumpToLatest(false);
    } else {
      setShowJumpToLatest(true);
    }
  }, [messages]);

  const handleSendQuestion = (question: string, scopeIds = selectedScopeIds) => {
    setActiveChunkId(null);
    setPreview(null);
    setActiveClaim("");
    conversation.sendQuestion(question, {
      scope_doc_ids: scopeIds.length > 0 ? scopeIds : undefined,
      collection: selectedCollection,
      top_k: topK,
      retrieval_mode: retrievalMode,
      model: selectedModel ?? undefined,
    });
  };

  // Scope Toggle
  const handleToggleScope = (doc_id: string) => {
    setSelectedScopeIds((prev) =>
      prev.includes(doc_id) ? prev.filter((id) => id !== doc_id) : [...prev, doc_id]
    );
  };

  const handleToggleCollectionScope = (docIds: string[]) => {
    setSelectedScopeIds((previousIds) => {
      const selectedEveryPage = docIds.every((docId) => previousIds.includes(docId));
      if (selectedEveryPage) {
        const collectionIds = new Set(docIds);
        return previousIds.filter((docId) => !collectionIds.has(docId));
      }
      return Array.from(new Set([...previousIds, ...docIds]));
    });
  };

  // Open Document / Chunk in Source Panel
  const handleOpenSourceByChunk = (chunkId: string, claim: string) => {
    setActiveChunkId(chunkId);
    setActiveClaim(claim);
    setPreview(null);
    setActiveTabMobile("evidence");
  };

  const handleOpenSourceByDoc = (docId: string) => {
    setActiveChunkId(`${docId}:0`);
    setActiveClaim("");
    setPreview(null);
    setActiveTabMobile("evidence");
  };

  // Page Actions
  const handlePageAdded = (newPage: Page) => library.addPage(newPage);

  const handleRefetch = async (doc_id: string) => {
    await refetchPage(doc_id);
    await loadLibraryData();
  };

  const handleRemove = async (doc_id: string) => {
    await deletePage(doc_id);
    library.removePage(doc_id);
    setSelectedScopeIds((prev) => prev.filter((id) => id !== doc_id));
    if (activeChunkId?.startsWith(doc_id)) {
      setActiveChunkId(null);
    }
  };

  const handleClearLibrary = async () => {
    await clearLibrary();
    conversation.clear();
    library.clearPages();
    setSelectedScopeIds([]);
    setActiveChunkId(null);
    setPreview(null);
    setActiveClaim("");
  };

  // Suggested questions from saved titles
  const suggestedQuestions = suggestedQuestionsForPages(pages);
  const latestAssistantMessage = [...messages]
    .reverse()
    .find((message) => message.role === "assistant");
  const collections = Array.from(
    pages.reduce((counts, page) => {
      counts.set(page.collection, (counts.get(page.collection) ?? 0) + 1);
      return counts;
    }, new Map<string, number>()),
  );
  const otherCollections = collections.filter(([name]) => name !== selectedCollection);

  return (
    <div className="flex h-dvh w-screen flex-col overflow-hidden bg-bg text-text font-sans">
      <a
        href="#question-input"
        className="sr-only z-50 focus:not-sr-only focus:absolute focus:left-3 focus:top-3 focus:rounded-ctrl focus:bg-surface focus:px-3 focus:py-2 focus:text-text"
      >
        {strings.skipToComposer}
      </a>
      {/* Offline Backend Banner */}
      {!backendOnline && (
        <div
          role="status"
          className="flex items-center justify-between border-b border-warn bg-warn/15 px-4 py-1.5 text-xs text-text"
        >
          <div className="flex items-center gap-2">
            <WifiOff className="w-4 h-4 text-warn" />
            <span>
              {pagesError instanceof Error
                ? pagesError.message
                : `${strings.cannotReachBackend} `}
              {!pagesError && <code className="font-mono">{getApiBaseUrl()}</code>}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={loadLibraryData}
              className="px-2 py-0.5 rounded bg-surface border border-line text-xs font-medium hover:bg-surface-2 flex items-center gap-1"
            >
              <RefreshCw className="w-3 h-3" /> {strings.retry}
            </button>
            <button
              onClick={() => setSettingsOpen(true)}
              className="text-xs text-accent underline ml-1"
            >
              {strings.configure}
            </button>
          </div>
        </div>
      )}

      <div className="relative flex min-h-0 flex-1 w-full overflow-hidden">
        {/* 1. LEFT: Library Column (Desktop & Drawer) */}
        <div
          className={`${
            libraryCollapsed ? "w-14" : "w-72"
          } relative h-full shrink-0 hidden lg:block transition-all duration-150 ${
            !libraryCollapsed ? "max-xl:absolute max-xl:left-0 max-xl:top-0 max-xl:z-30" : ""
          }`}
        >
          {libraryCollapsed ? (
            <div className="h-full w-14 bg-rail border-r border-line flex flex-col items-center py-4 space-y-4">
              <button
                onClick={() => setLibraryCollapsed(false)}
                className="p-2 rounded hover:bg-surface-2 text-text-muted hover:text-text transition-colors"
                title={strings.titleExpandLibrary}
                aria-label={strings.titleExpandLibrary}
              >
                <BookOpen className="w-5 h-5" />
                <span className="text-xs tabular-nums">{pages.length}</span>
              </button>
            </div>
          ) : (
            <LibraryPanel
              pages={pages}
              selectedScopeIds={selectedScopeIds}
              onToggleScope={handleToggleScope}
              onToggleCollectionScope={handleToggleCollectionScope}
              onClearScope={() => setSelectedScopeIds([])}
              onPageAdded={handlePageAdded}
              onOpenSource={handleOpenSourceByDoc}
              onRefetch={handleRefetch}
              onRemove={handleRemove}
              selectedCollection={selectedCollection}
              onSelectCollection={setSelectedCollection}
              onCollapseRail={() => setLibraryCollapsed(true)}
            />
          )}
        </div>

        {/* 2. CENTER: Ask Column */}
        <main
          aria-label={strings.ariaConversation}
          className={`relative flex h-full min-w-0 flex-1 flex-col overflow-hidden bg-bg ${
            activeTabMobile !== "ask" ? "hidden lg:flex" : "flex"
          }`}
        >
          {/* Top Bar */}
          <header className="flex h-12 shrink-0 items-center justify-between border-b border-line bg-surface/50 px-4">
            <div className="flex min-w-0 items-center gap-3">
              <span className="shrink-0 font-semibold text-base text-text">WebRAG</span>
              <span className="hidden text-sm text-text-muted lg:inline">The Reading Room</span>
              <span className="hidden items-center gap-1.5 text-xs text-text-muted sm:inline-flex">
                <span
                  className={`h-2 w-2 rounded-full ${
                    isMockMode() ? "bg-warn" : backendOnline ? "bg-ok" : "bg-err"
                  }`}
                />
                {isMockMode()
                  ? strings.demoData
                  : backendOnline
                    ? strings.connected
                    : strings.offline}
              </span>
              {(selectedModel || modelName) && (
                <span className="hidden max-w-40 truncate text-xs text-text-muted md:inline">
                  {selectedModel || modelName}
                </span>
              )}
              {backendOnline && !selectedModel && !modelName && !isMockMode() && (
                <button
                  type="button"
                  onClick={() => setSettingsOpen(true)}
                  className="hidden text-xs text-accent underline md:inline"
                >
                  {strings.selectGenerationModel}
                </button>
              )}
            </div>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setSettingsOpen(true)}
                className="flex min-h-9 min-w-9 items-center justify-center rounded text-text-muted transition-colors hover:bg-surface-2 hover:text-text"
                title={strings.settings}
                aria-label={strings.settings}
              >
                <Settings className="h-4 w-4" />
              </button>
            </div>
          </header>

          {/* Conversation Thread */}
          <div
            ref={chatScrollRef}
            className="flex-1 overflow-y-auto px-4 py-6 max-w-[720px] w-full mx-auto"
            tabIndex={0}
            onScroll={handleChatScroll}
          >
            {messages.length === 0 ? (
              <div className="py-8 text-left space-y-5">
                <div className="space-y-2">
                  <h1 className="text-2xl font-medium text-text">
                    {strings.askAnything}
                  </h1>
                  <p className="max-w-xl text-sm leading-relaxed text-text-muted">
                    {strings.askExplanation}
                  </p>
                </div>

                {collections.length > 0 && (
                  <div className="flex flex-wrap gap-2" aria-label={strings.usePageCollection}>
                    {collections.map(([collection, count]) => (
                      <button
                        key={collection}
                        type="button"
                        onClick={() => setSelectedCollection(collection)}
                        aria-pressed={selectedCollection === collection}
                        className={`min-h-10 rounded-ctrl border px-3 text-sm transition-colors ${
                          selectedCollection === collection
                            ? "border-accent bg-accent-soft text-accent"
                            : "border-line bg-surface text-text hover:bg-surface-2"
                        }`}
                      >
                        {strings.savedCollectionCount(collection, count)}
                      </button>
                    ))}
                  </div>
                )}

                {suggestedQuestions.length > 0 && (
                  <div className="max-w-lg space-y-2 pt-2">
                    <span className="block text-sm text-text-muted">
                      {strings.suggestedQuestions}
                    </span>
                    {suggestedQuestions.map((question) => (
                      <button
                        key={question}
                        onClick={() => handleSendQuestion(question)}
                        className="block min-h-10 w-full rounded-ctrl border border-line bg-surface p-2.5 text-left text-sm text-text transition-colors hover:bg-surface-2"
                      >
                        {question}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            ) : (
              messages.map((msg, index) => {
                if (msg.role !== "assistant") return null;
                const question = messages[index - 1]?.role === "user"
                  ? messages[index - 1].content
                  : undefined;
                return (
                  <AnswerMessage
                    key={msg.id}
                    message={msg}
                    question={question}
                    onOpenSource={handleOpenSourceByChunk}
                    onPreviewSource={(chunkId, claim) =>
                      setPreview(chunkId ? { chunkId, claim } : null)
                    }
                    pinnedChunkId={activeChunkId}
                    previewedChunkId={preview?.chunkId ?? null}
                    isStreaming={isStreaming && msg.id === latestAssistantMessage?.id}
                    hasScope={selectedScopeIds.length > 0}
                    hasOtherCollections={otherCollections.length > 0}
                    onRegenerate={() => {
                      if (question) handleSendQuestion(question);
                    }}
                    onPrefillQuestion={handleSendQuestion}
                    onAddLinkFocus={() => {
                      if (window.innerWidth < 1024) setActiveTabMobile("library");
                      else setLibraryCollapsed(false);
                    }}
                    onSearchAllPages={(query) => handleSendQuestion(query, [])}
                    onSwitchCollection={() => {
                      if (otherCollections.length > 0) setSelectedCollection(otherCollections[0][0]);
                    }}
                  />
                );
              })
            )}
          </div>
          <div className="sr-only" role="status" aria-live="polite" aria-atomic="true">
            {isStreaming
              ? [...messages].reverse().find((message) => message.role === "assistant")?.stage ||
                strings.writingAnswer
              : ""}
          </div>
          {showJumpToLatest && (
            <button
              type="button"
              onClick={() => {
                const scrollContainer = chatScrollRef.current;
                if (!scrollContainer) return;
                scrollContainer.scrollTop = scrollContainer.scrollHeight;
                isNearBottomRef.current = true;
                setShowJumpToLatest(false);
              }}
              className="absolute bottom-28 right-6 rounded-ctrl border border-line bg-surface px-3 py-2 text-sm text-text shadow-sm hover:bg-surface-2"
            >
              {strings.jumpToLatest}
            </button>
          )}

          {/* Fixed Composer at bottom */}
          <footer className="border-t border-line/60 bg-bg shrink-0">
            <Composer
              onSend={handleSendQuestion}
              onStop={conversation.stop}
              isStreaming={isStreaming}
              selectedScopeIds={selectedScopeIds}
              onClearScope={() => setSelectedScopeIds([])}
              retrievalMode={retrievalMode}
              onToggleRetrievalMode={setRetrievalMode}
              topK={topK}
              onTopKChange={setTopK}
            />
          </footer>

        </main>

        {/* 3. Mobile Library Fullscreen View when activeTabMobile === "library" */}
        {activeTabMobile === "library" && (
          <div className="lg:hidden fixed inset-0 z-40 bg-surface flex flex-col">
            <div className="p-3 border-b border-line flex items-center justify-between">
              <span className="font-medium text-base">{strings.savedPages}</span>
              <button
                onClick={() => setActiveTabMobile("ask")}
                className="px-3 py-1 rounded bg-surface-2 text-xs font-mono"
              >
                {strings.done}
              </button>
            </div>
            <div className="flex-1 overflow-hidden">
              <LibraryPanel
                pages={pages}
                selectedScopeIds={selectedScopeIds}
                onToggleScope={handleToggleScope}
                onToggleCollectionScope={handleToggleCollectionScope}
                onClearScope={() => setSelectedScopeIds([])}
                onPageAdded={handlePageAdded}
                onOpenSource={handleOpenSourceByDoc}
                onRefetch={handleRefetch}
                onRemove={handleRemove}
                selectedCollection={selectedCollection}
                onSelectCollection={setSelectedCollection}
                onCollapseRail={() => setActiveTabMobile("ask")}
              />
            </div>
          </div>
        )}

        {/* 4. RIGHT: Source Panel (Context Passage & Citations) */}
        <SourcePanel
          chunkId={preview?.chunkId ?? activeChunkId}
          pinnedChunkId={activeChunkId}
          previewedChunkId={preview?.chunkId ?? null}
          citations={(latestAssistantMessage?.citations ?? []).filter((citation) =>
            new RegExp(`\\[${citation.n}\\]`).test(latestAssistantMessage?.content ?? ""),
          )}
          retrieved={latestAssistantMessage?.retrieved ?? []}
          highlightClaim={preview?.claim || activeClaim}
          mobileOpen={activeTabMobile === "evidence"}
          onClose={() => {
            setActiveChunkId(null);
            setPreview(null);
            setActiveClaim("");
            setActiveTabMobile("ask");
          }}
          onSelectCitation={(chunkId) => {
            setActiveChunkId(chunkId);
            setPreview(null);
            const citation = latestAssistantMessage?.citations?.find((item) => item.chunk_id === chunkId);
            setActiveClaim(
              citation && latestAssistantMessage
                ? claimForCitation(latestAssistantMessage.content, citation.n)
                : latestAssistantMessage?.content ?? "",
            );
          }}
        />

        {/* 5. Settings Drawer */}
        <SettingsDrawer
          isOpen={settingsOpen}
          onClose={() => setSettingsOpen(false)}
          theme={theme}
          onThemeChange={setTheme}
          topK={topK}
          onTopKChange={setTopK}
          onClearLibrary={handleClearLibrary}
          onRefresh={() => void loadLibraryData()}
          selectedModel={selectedModel}
          onModelChange={handleModelChange}
        />
      </div>
      <nav
        className={`grid h-14 shrink-0 grid-cols-3 border-t border-line bg-surface text-sm lg:hidden ${
          activeTabMobile === "library" ? "hidden" : ""
        }`}
        aria-label={strings.mobileNavigation}
      >
        <button
          type="button"
          onClick={() => setActiveTabMobile("ask")}
          aria-current={activeTabMobile === "ask" ? "page" : undefined}
          className={`min-h-12 ${activeTabMobile === "ask" ? "border-t-2 border-accent text-accent" : "text-text-muted"}`}
        >
          {strings.askTab}
        </button>
        <button
          type="button"
          onClick={() => setActiveTabMobile("evidence")}
          aria-current={activeTabMobile === "evidence" ? "page" : undefined}
          className={`min-h-12 ${activeTabMobile === "evidence" ? "border-t-2 border-accent text-accent" : "text-text-muted"}`}
        >
          {strings.ariaEvidenceTab} ({latestAssistantMessage?.citations?.length ?? 0})
        </button>
        <button
          type="button"
          onClick={() => setActiveTabMobile("library")}
          aria-current={activeTabMobile === "library" ? "page" : undefined}
          className="min-h-12 text-text-muted"
        >
          {strings.libraryTabCount(pages.length)}
        </button>
      </nav>
    </div>
  );
};
export default App;
