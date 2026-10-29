import React, { useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import type { Citation, RetrievedPassage } from "../../api/types";
import { strings } from "../../strings";

interface CitationChipProps {
  n: number;
  citation?: Citation;
  retrievedPassage?: RetrievedPassage;
  onOpenSource: (chunkId: string, claim: string) => void;
  onPreviewSource: (chunkId: string | null, claim: string) => void;
  claim: string;
  isPinned: boolean;
  isPreviewed: boolean;
}

export const CitationChip: React.FC<CitationChipProps> = ({
  n,
  citation,
  retrievedPassage,
  onOpenSource,
  onPreviewSource,
  claim,
  isPinned,
  isPreviewed,
}) => {
  const [showPopover, setShowPopover] = useState(false);
  const [popoverPosition, setPopoverPosition] = useState<{
    top: number;
    left: number;
  } | null>(null);
  const triggerRef = useRef<HTMLSpanElement>(null);
  const popoverRef = useRef<HTMLSpanElement>(null);
  const closeTimerRef = useRef<number | null>(null);

  const title = citation?.title || retrievedPassage?.title || strings.fallbackSource(n);
  const url = citation?.url || retrievedPassage?.url || "";
  let domain = "";
  try {
    domain = url ? new URL(url).hostname : "";
  } catch {
    domain = "";
  }
  const snippet = retrievedPassage?.snippet || strings.noPassagePreview;
  const chunkId = citation?.chunk_id || retrievedPassage?.chunk_id || "";

  const clearCloseTimer = () => {
    if (closeTimerRef.current !== null) {
      window.clearTimeout(closeTimerRef.current);
      closeTimerRef.current = null;
    }
  };

  const openPopover = () => {
    clearCloseTimer();
    setShowPopover(true);
    onPreviewSource(chunkId || null, claim);
  };

  const closePopover = () => {
    clearCloseTimer();
    closeTimerRef.current = window.setTimeout(() => {
      setShowPopover(false);
      setPopoverPosition(null);
      onPreviewSource(null, "");
      closeTimerRef.current = null;
    }, 120);
  };

  useLayoutEffect(() => {
    if (!showPopover) return;

    const updatePosition = () => {
      const trigger = triggerRef.current?.getBoundingClientRect();
      const popover = popoverRef.current;
      if (!trigger || !popover) return;

      const bounds = popover.getBoundingClientRect();
      const gap = 8;
      const margin = 8;
      const above = trigger.top >= bounds.height + gap;
      const preferredTop = above ? trigger.top - bounds.height - gap : trigger.bottom + gap;
      const top = Math.max(
        margin,
        Math.min(preferredTop, window.innerHeight - bounds.height - margin),
      );
      const preferredLeft = trigger.left + trigger.width / 2 - bounds.width / 2;
      const left = Math.max(
        margin,
        Math.min(preferredLeft, window.innerWidth - bounds.width - margin),
      );
      setPopoverPosition({ top, left });
    };

    updatePosition();
    window.addEventListener("resize", updatePosition);
    window.addEventListener("scroll", updatePosition, true);
    return () => {
      window.removeEventListener("resize", updatePosition);
      window.removeEventListener("scroll", updatePosition, true);
    };
  }, [showPopover]);

  useLayoutEffect(
    () => () => {
      clearCloseTimer();
    },
    [],
  );

  const handleClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (chunkId) {
      onOpenSource(chunkId, claim);
    }
  };

  return (
    <span
      ref={triggerRef}
      className="relative inline-block"
      onMouseEnter={openPopover}
      onMouseLeave={closePopover}
      onFocus={openPopover}
      onBlur={() => {
        clearCloseTimer();
        setShowPopover(false);
        setPopoverPosition(null);
        onPreviewSource(null, "");
      }}
    >
      <button
        type="button"
        onClick={handleClick}
        className="citation-chip mx-0.5"
        aria-pressed={isPinned}
        data-previewed={isPreviewed}
        aria-label={strings.sourceLabel(n, title)}
      >
        [{n}]
      </button>

      {/* Popover Card */}
      {showPopover &&
        createPortal(
          <span
            ref={popoverRef}
            role="tooltip"
            className="citation-popover rounded-ctrl border border-line bg-surface p-3 text-left shadow-lg"
            style={{
              top: popoverPosition?.top ?? 0,
              left: popoverPosition?.left ?? 0,
              visibility: popoverPosition ? "visible" : "hidden",
            }}
            onMouseEnter={clearCloseTimer}
            onMouseLeave={closePopover}
          >
            <span className="mb-1.5 flex items-start justify-between gap-2 border-b border-line pb-1.5">
              <span className="block min-w-0 truncate font-sans text-xs font-medium text-text">
                {title}
              </span>
              <span className="shrink-0 rounded bg-accent-soft px-1 font-mono text-[10px] text-accent">
                [{n}]
              </span>
            </span>

            <span className="citation-preview-snippet mb-2 block line-clamp-3 text-text-muted">
              "{snippet}"
            </span>

            <span className="flex items-center justify-between gap-2 border-t border-line/50 pt-1 text-[11px] text-text-muted">
              <span className="truncate">{domain}</span>
              <span className="flex shrink-0 items-center gap-0.5 text-accent hover:underline">
                {strings.openPassageHint} →
              </span>
            </span>
          </span>,
          document.body,
        )}
    </span>
  );
};
