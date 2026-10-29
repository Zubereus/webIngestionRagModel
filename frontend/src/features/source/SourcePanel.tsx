import React, { useEffect, useMemo, useState } from "react";
import {
  Check,
  ChevronLeft,
  ChevronRight,
  Copy,
  ExternalLink,
  Pin,
  X,
} from "lucide-react";
import type { Chunk, Citation, RetrievedPassage } from "../../api/types";
import { fetchChunk } from "../../api/client";
import { bestSentenceIndex, splitSentences } from "../../lib/trace";
import { strings } from "../../strings";

interface SourcePanelProps {
  chunkId: string | null;
  pinnedChunkId: string | null;
  previewedChunkId: string | null;
  citations: Citation[];
  retrieved: RetrievedPassage[];
  highlightClaim: string;
  mobileOpen: boolean;
  onClose: () => void;
  onSelectCitation: (chunkId: string) => void;
}

interface EvidenceItem {
  chunkId: string;
  number: number;
  title: string;
  url: string;
  snippet: string;
  score: number;
  denseScore?: number;
  bm25Score?: number;
}

function domainFromUrl(url: string): string {
  try {
    return new URL(url).hostname;
  } catch {
    return "";
  }
}

export const SourcePanel: React.FC<SourcePanelProps> = ({
  chunkId,
  pinnedChunkId,
  previewedChunkId,
  citations,
  retrieved,
  highlightClaim,
  mobileOpen,
  onClose,
  onSelectCitation,
}) => {
  const [activeTab, setActiveTab] = useState<"cited" | "retrieved">("cited");
  const [chunk, setChunk] = useState<Chunk | null>(null);
  const [loadError, setLoadError] = useState<{ chunkId: string; message: string } | null>(null);
  const [showSurroundingText, setShowSurroundingText] = useState(false);
  const [copied, setCopied] = useState(false);
  const [copyError, setCopyError] = useState(false);
  const cardRefs = React.useRef(new Map<string, HTMLElement>());

  const citedItems: EvidenceItem[] = useMemo(
    () =>
      citations.map((citation) => {
        const passage = retrieved.find((item) => item.chunk_id === citation.chunk_id);
        return {
          chunkId: citation.chunk_id,
          number: citation.n,
          title: citation.title,
          url: citation.url,
          snippet: passage?.snippet ?? "",
          score: citation.score,
          denseScore: passage?.dense_score,
          bm25Score: passage?.bm25_score,
        };
      }),
    [citations, retrieved],
  );
  const retrievedItems: EvidenceItem[] = useMemo(
    () =>
      retrieved.map((passage) => {
        const citation = citations.find((item) => item.chunk_id === passage.chunk_id);
        return {
          chunkId: passage.chunk_id,
          number: citation?.n ?? passage.rank,
          title: passage.title,
          url: passage.url,
          snippet: passage.snippet,
          score: passage.score,
          denseScore: passage.dense_score,
          bm25Score: passage.bm25_score,
        };
      }),
    [citations, retrieved],
  );
  const items = activeTab === "cited" ? citedItems : retrievedItems;
  const selectedIndex = items.findIndex((item) => item.chunkId === chunkId);

  useEffect(() => {
    if (!chunkId) {
      return;
    }

    let active = true;
    fetchChunk(chunkId)
      .then((data) => {
        if (active) setChunk(data);
      })
      .catch((error: unknown) => {
        if (active) {
          setLoadError({
            chunkId,
            message: error instanceof Error ? error.message : strings.loadPassageError,
          });
        }
      })

    return () => {
      active = false;
    };
  }, [chunkId]);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      const target = event.target;
      if (
        target instanceof HTMLElement &&
        (target.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName))
      ) {
        return;
      }

      if (event.key === "[" && selectedIndex > 0) {
        onSelectCitation(items[selectedIndex - 1].chunkId);
      } else if (event.key === "]" && selectedIndex >= 0 && selectedIndex < items.length - 1) {
        onSelectCitation(items[selectedIndex + 1].chunkId);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [items, onSelectCitation, selectedIndex]);

  const sentences = chunk ? splitSentences(chunk.text) : [];
  const highlightIndex = chunk
    ? bestSentenceIndex(highlightClaim, splitSentences(chunk.text))
    : -1;
  const selectedItem = items.find((item) => item.chunkId === chunkId);
  const currentLoadError = loadError?.chunkId === chunkId ? loadError.message : null;
  const loading = Boolean(chunkId && chunk?.chunk_id !== chunkId && !currentLoadError);

  useEffect(() => {
    if (pinnedChunkId) {
      cardRefs.current.get(pinnedChunkId)?.scrollIntoView({
        behavior: "smooth",
        block: "nearest",
      });
    }
  }, [pinnedChunkId]);

  const handleCopyQuote = async () => {
    if (!chunk) return;
    try {
      await navigator.clipboard.writeText(`“${chunk.text}”\n${chunk.url}`);
      setCopyError(false);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1800);
    } catch {
      setCopyError(true);
    }
  };

  return (
    <aside
      aria-label={strings.evidence}
      className={`${
        mobileOpen
          ? "fixed inset-x-0 bottom-14 top-0 z-40 flex h-auto"
          : "hidden lg:flex"
      } w-full shrink-0 flex-col border-l border-line bg-surface lg:static lg:h-full lg:w-[360px] xl:w-[400px]`}
    >
      <header className="flex items-center justify-between border-b border-line px-4 py-3">
        <div>
          <h2 className="text-base font-semibold text-text">{strings.evidence}</h2>
          <p className="text-xs text-text-muted">{strings.evidenceHint}</p>
        </div>
        {(pinnedChunkId || mobileOpen) && (
          <button
            type="button"
            onClick={onClose}
            className="flex min-h-9 min-w-9 items-center justify-center rounded text-text-muted hover:bg-surface-2 hover:text-text"
            aria-label={mobileOpen ? strings.close : strings.clearPinnedEvidence}
            title={mobileOpen ? strings.close : strings.clearPinnedEvidence}
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </header>

      <div className="grid grid-cols-2 border-b border-line p-2" role="tablist">
        <button
          type="button"
          role="tab"
          aria-selected={activeTab === "cited"}
          onClick={() => setActiveTab("cited")}
          className={`min-h-10 rounded text-sm ${
            activeTab === "cited" ? "bg-surface-2 font-medium text-text" : "text-text-muted"
          }`}
        >
          {strings.citedTab} ({citedItems.length})
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={activeTab === "retrieved"}
          onClick={() => setActiveTab("retrieved")}
          className={`min-h-10 rounded text-sm ${
            activeTab === "retrieved" ? "bg-surface-2 font-medium text-text" : "text-text-muted"
          }`}
        >
          {strings.retrievedTab} ({retrievedItems.length})
        </button>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto">
        {items.length === 0 ? (
          <p className="p-4 text-sm text-text-muted">{strings.evidenceEmpty}</p>
        ) : (
          <div className="space-y-2 border-b border-line p-3">
            {items.map((item) => (
              <article
                ref={(element) => {
                  if (element) cardRefs.current.set(item.chunkId, element);
                  else cardRefs.current.delete(item.chunkId);
                }}
                key={`${item.chunkId}-${item.number}`}
                className={`rounded-ctrl border p-3 transition-opacity ${
                  item.chunkId === pinnedChunkId
                    ? "border-accent bg-surface"
                    : item.chunkId === previewedChunkId
                      ? "border-line bg-surface"
                      : previewedChunkId
                        ? "border-line bg-bg opacity-60"
                        : "border-line bg-bg"
                }`}
              >
                <button
                  type="button"
                  onClick={() => onSelectCitation(item.chunkId)}
                  className="w-full text-left"
                  title={strings.pinPassage}
                >
                  <span className="mb-1 flex items-center justify-between gap-2">
                    <span className="line-clamp-2 text-sm font-medium text-text">{item.title}</span>
                    <span className="shrink-0 rounded bg-surface-2 px-1.5 py-0.5 text-xs text-accent">
                      [{item.number}]
                    </span>
                  </span>
                  <span className="passage line-clamp-3 text-sm leading-7 text-text">
                    {item.snippet || strings.loadingPassage}
                  </span>
                </button>
                <div className="mt-2 flex items-center justify-between text-xs text-text-muted">
                  <span className="flex min-w-0 flex-col gap-y-1">
                    <span className="tabular-nums">{strings.matchScore(item.score.toFixed(2))}</span>
                    <span className="truncate">{domainFromUrl(item.url)}{chunk?.chunk_id === item.chunkId && chunk.section_path.length > 0 ? ` › ${chunk.section_path.join(" › ")}` : ""}</span>
                    {item.denseScore !== undefined && (
                      <span>{strings.denseScore} {item.denseScore.toFixed(2)}</span>
                    )}
                    {item.bm25Score !== undefined && (
                      <span>{strings.bm25Score} {item.bm25Score.toFixed(2)}</span>
                    )}
                  </span>
                  <div className="flex items-center gap-1">
                    <button
                      type="button"
                      onClick={() => onSelectCitation(item.chunkId)}
                      className="inline-flex min-h-8 items-center gap-1 rounded px-2 text-text hover:bg-surface-2"
                      title={strings.pinPassage}
                    >
                      <Pin className="h-3 w-3" />
                      {strings.pinPassage}
                    </button>
                    <a
                      href={item.url}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex min-h-8 items-center gap-1 rounded px-2 hover:bg-surface-2"
                      title={strings.openPage}
                    >
                      <ExternalLink className="h-3 w-3" />
                      {strings.openPage}
                    </a>
                  </div>
                </div>
              </article>
            ))}
          </div>
        )}

        {chunkId && (
          <section className="space-y-3 p-4">
            {loading ? (
              <p className="text-sm text-text-muted">{strings.loadingPassage}</p>
            ) : currentLoadError ? (
              <p role="alert" className="text-sm text-err">{currentLoadError}</p>
            ) : chunk ? (
              <>
                <div className="flex items-start justify-between gap-3">
                  <h3 className="text-sm font-semibold leading-snug text-text">{chunk.title}</h3>
                  {selectedItem?.url && (
                    <a
                      href={selectedItem.url}
                      target="_blank"
                      rel="noreferrer"
                      aria-label={strings.openPage}
                      title={strings.openPage}
                      className="flex min-h-9 min-w-9 shrink-0 items-center justify-center rounded text-text-muted hover:bg-surface-2"
                    >
                      <ExternalLink className="h-4 w-4" />
                    </a>
                  )}
                </div>
                <div className="passage rounded-ctrl border-l-2 border-accent bg-accent-soft/50 p-3 text-text">
                  {sentences.map((sentence, index) =>
                    index === highlightIndex ? (
                      <mark
                        key={index}
                        title={strings.sharedWordsTooltip}
                        aria-label={strings.sharedWordsTooltip}
                      >
                        {sentence}{" "}
                      </mark>
                    ) : (
                      <React.Fragment key={index}>{sentence}{" "}</React.Fragment>
                    ),
                  )}
                </div>
                {highlightIndex === -1 && (
                  <p className="text-xs text-text-muted">{strings.noSingleSentence}</p>
                )}
                <button
                  type="button"
                  onClick={() => setShowSurroundingText((value) => !value)}
                  className="min-h-9 text-sm text-accent hover:underline"
                  aria-expanded={showSurroundingText}
                >
                  {showSurroundingText ? strings.hideSurroundingText : strings.showSurroundingText}
                </button>
                {showSurroundingText && (
                  <div className="space-y-3 text-sm text-text-muted">
                    {chunk.context_before && <p className="passage">{chunk.context_before}</p>}
                    {chunk.context_after && <p className="passage">{chunk.context_after}</p>}
                  </div>
                )}
                <button
                  type="button"
                  onClick={() => void handleCopyQuote()}
                  className="inline-flex min-h-10 items-center gap-2 rounded-ctrl border border-line px-3 text-sm text-text hover:bg-surface-2"
                >
                  {copied ? <Check className="h-4 w-4 text-ok" /> : <Copy className="h-4 w-4" />}
                  {copied ? strings.copied : strings.copyQuoteWithLink}
                </button>
                {copyError && (
                  <p role="alert" className="text-xs text-err">{strings.copyFailed}</p>
                )}
              </>
            ) : null}
          </section>
        )}
      </div>

      <footer className="flex items-center justify-between border-t border-line px-3 py-2 text-xs text-text-muted">
        <button
          type="button"
          disabled={selectedIndex <= 0}
          onClick={() => onSelectCitation(items[selectedIndex - 1].chunkId)}
          className="inline-flex min-h-9 items-center gap-1 rounded px-2 hover:bg-surface-2 disabled:opacity-40"
        >
          <ChevronLeft className="h-4 w-4" />
          {strings.previous}
        </button>
        <span>
          {selectedIndex >= 0 ? `${selectedIndex + 1} / ${items.length}` : strings.noSelection}
        </span>
        <button
          type="button"
          disabled={selectedIndex < 0 || selectedIndex >= items.length - 1}
          onClick={() => onSelectCitation(items[selectedIndex + 1].chunkId)}
          className="inline-flex min-h-9 items-center gap-1 rounded px-2 hover:bg-surface-2 disabled:opacity-40"
        >
          {strings.next}
          <ChevronRight className="h-4 w-4" />
        </button>
      </footer>
    </aside>
  );
};
