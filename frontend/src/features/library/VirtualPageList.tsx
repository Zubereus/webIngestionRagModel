import React, { useEffect } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import type { Page } from "../../api/types";

interface VirtualPageListProps {
  pages: Page[];
  scrollElementRef: React.RefObject<HTMLDivElement | null>;
  highlightedPageId: string | null;
  renderPageRow: (page: Page) => React.ReactNode;
}

export const VirtualPageList: React.FC<VirtualPageListProps> = ({
  pages,
  scrollElementRef,
  highlightedPageId,
  renderPageRow,
}) => {
  // oxlint-disable-next-line react/incompatible-library
  const virtualizer = useVirtualizer({
    count: pages.length,
    getScrollElement: () => scrollElementRef.current,
    estimateSize: () => 112,
    getItemKey: (index) => pages[index]?.doc_id ?? index,
    overscan: 8,
  });

  useEffect(() => {
    if (!highlightedPageId) return;
    const index = pages.findIndex((page) => page.doc_id === highlightedPageId);
    if (index >= 0) virtualizer.scrollToIndex(index, { align: "center" });
  }, [highlightedPageId, pages, virtualizer]);

  return (
    <div className="relative w-full" style={{ height: `${virtualizer.getTotalSize()}px` }}>
      {virtualizer.getVirtualItems().map((virtualItem) => (
        <div
          key={virtualItem.key}
          data-index={virtualItem.index}
          ref={virtualizer.measureElement}
          className="absolute left-0 top-0 w-full pb-1"
          style={{ transform: `translateY(${virtualItem.start}px)` }}
        >
          {renderPageRow(pages[virtualItem.index])}
        </div>
      ))}
    </div>
  );
};
