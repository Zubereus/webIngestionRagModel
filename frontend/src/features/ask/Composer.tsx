import React, { useEffect, useRef, useState } from "react";
import { ArrowUp, Square, SlidersHorizontal, X } from "lucide-react";
import { strings } from "../../strings";

interface ComposerProps {
  onSend: (question: string) => void;
  onStop: () => void;
  isStreaming: boolean;
  selectedScopeIds: string[];
  onClearScope: () => void;
  retrievalMode: "hybrid" | "dense";
  onToggleRetrievalMode: (mode: "hybrid" | "dense") => void;
  topK: number;
  onTopKChange: (count: number) => void;
}

export const Composer: React.FC<ComposerProps> = ({
  onSend,
  onStop,
  isStreaming,
  selectedScopeIds,
  onClearScope,
  retrievalMode,
  onToggleRetrievalMode,
  topK,
  onTopKChange,
}) => {
  const [text, setText] = useState("");
  const [showSettings, setShowSettings] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Keep the composer compact; longer questions scroll within the field.
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 140)}px`;
    }
  }, [text]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (
      e.key === "Enter" &&
      !e.shiftKey &&
      !e.nativeEvent.isComposing
    ) {
      e.preventDefault();
      if (!isStreaming && text.trim()) {
        onSend(text.trim());
        setText("");
      }
    }
  };

  const handleSendClick = () => {
    if (isStreaming) {
      onStop();
    } else if (text.trim()) {
      onSend(text.trim());
      setText("");
    }
  };

  return (
    <div className="w-full max-w-[720px] mx-auto p-4">
      {/* Scope Chip above composer */}
      {selectedScopeIds.length > 0 && (
        <div className="mb-2 flex items-center gap-1.5">
          <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-ctrl bg-accent-soft border border-line text-xs text-accent">
            <span className="font-medium">
              {strings.scopeLabel}: {strings.pageCountLabel(selectedScopeIds.length)}
            </span>
            <button
              onClick={onClearScope}
              className="p-0.5 hover:opacity-75 rounded"
              title={strings.clearScope}
              aria-label={strings.clearScope}
            >
              <X className="w-3 h-3" />
            </button>
          </div>
        </div>
      )}

      {/* Main Composer Box */}
      <div className="relative bg-surface rounded-pnl border border-line focus-within:border-accent transition-colors">
        <div className="relative">
          <textarea
            ref={textareaRef}
            rows={1}
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={handleKeyDown}
            id="question-input"
            placeholder={strings.askPlaceholder}
            className="composer-input min-h-[58px] max-h-[140px] w-full resize-none overflow-y-auto rounded-t-pnl bg-transparent px-4 py-4 pr-16 text-base leading-6 text-text placeholder:text-text-muted focus:outline-none focus-visible:outline-none font-sans"
            aria-label={strings.questionInputLabel}
          />

          {/* Action Button: Send or Stop */}
          <div className="absolute right-3 bottom-3 flex items-center gap-2">
            <button
              onClick={handleSendClick}
              disabled={!isStreaming && !text.trim()}
              className={`min-h-10 min-w-10 rounded-ctrl transition-colors flex items-center justify-center ${
                isStreaming
                  ? "bg-err text-bg hover:opacity-90"
                  : text.trim()
                  ? "bg-accent text-bg hover:opacity-90 shadow-sm"
                  : "bg-surface-2 text-text-muted cursor-not-allowed opacity-50"
              }`}
              title={isStreaming ? strings.stopGeneration : strings.sendQuestionShortcut}
              aria-label={isStreaming ? strings.stopGeneration : strings.sendQuestion}
            >
              {isStreaming ? (
                <Square className="w-4 h-4 fill-current" />
              ) : (
                <ArrowUp className="w-4 h-4 stroke-[2.5]" />
              )}
            </button>
          </div>
        </div>

        {/* Bottom Tool row */}
        <div className="px-3 pb-2.5 pt-0 flex items-center justify-between text-xs text-text-muted border-t border-line/40">
          <div className="flex items-center gap-3">
            {/* Retrieval Mode selector */}
            <div className="relative">
              <button
                type="button"
                onClick={() => setShowSettings(!showSettings)}
                className="flex items-center gap-1 hover:text-text transition-colors py-0.5"
                title={strings.retrievalConfiguration}
                aria-expanded={showSettings}
                aria-haspopup="dialog"
              >
                <SlidersHorizontal className="w-3.5 h-3.5" />
                <span>{strings.searchOptions}</span>
              </button>

              {showSettings && (
                <div
                  role="dialog"
                  aria-label={strings.searchOptions}
                  className="absolute bottom-full left-0 z-20 mb-2 w-72 space-y-2 rounded-ctrl border border-line bg-surface p-3 shadow-md"
                >
                  <button
                    type="button"
                    onClick={() => {
                      onToggleRetrievalMode("hybrid");
                      setShowSettings(false);
                    }}
                    className={`w-full rounded px-2 py-2 text-left text-sm transition-colors ${
                      retrievalMode === "hybrid"
                        ? "bg-accent-soft text-accent font-medium"
                        : "hover:bg-surface-2"
                    }`}
                  >
                    <span className="block font-medium">{strings.hybridSearch}</span>
                    <span className="block text-xs text-text-muted">{strings.hybridDescription}</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      onToggleRetrievalMode("dense");
                      setShowSettings(false);
                    }}
                    className={`w-full rounded px-2 py-2 text-left text-sm transition-colors ${
                      retrievalMode === "dense"
                        ? "bg-accent-soft text-accent font-medium"
                        : "hover:bg-surface-2"
                    }`}
                  >
                    <span className="block font-medium">{strings.denseSearch}</span>
                    <span className="block text-xs text-text-muted">{strings.denseDescription}</span>
                  </button>
                  <label className="block border-t border-line pt-2 text-xs text-text-muted">
                    <span className="mb-1 flex justify-between">
                      <span>{strings.passageCount}</span>
                      <span>{topK} {strings.passagesUnit}</span>
                    </span>
                    <input
                      type="range"
                      min={1}
                      max={10}
                      value={topK}
                      onChange={(event) => onTopKChange(Number(event.target.value))}
                      className="w-full accent-accent"
                    />
                  </label>
                </div>
              )}
            </div>
          </div>

          <span className="text-[11px] text-text-muted/80">
            {strings.shiftEnterHint}
          </span>
        </div>
      </div>
    </div>
  );
};
