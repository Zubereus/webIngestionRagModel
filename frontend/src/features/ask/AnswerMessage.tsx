import React, { useContext, useState } from "react";
import type { ReactNode } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Check, Copy, RotateCw, Clock } from "lucide-react";
import type { AskMessage } from "../../api/types";
import { CitationChip } from "./CitationChip";
import { strings } from "../../strings";
import { claimForCitation } from "../../lib/trace";

interface AnswerMessageProps {
  message: AskMessage;
  question?: string;
  onOpenSource: (chunkId: string, claim: string) => void;
  onPreviewSource: (chunkId: string | null, claim: string) => void;
  pinnedChunkId: string | null;
  previewedChunkId: string | null;
  isStreaming: boolean;
  hasScope: boolean;
  hasOtherCollections: boolean;
  onRegenerate?: () => void;
  onPrefillQuestion?: (question: string) => void;
  onAddLinkFocus?: () => void;
  onSearchAllPages?: (question: string) => void;
  onSwitchCollection?: () => void;
}

interface CitationRenderContext {
  message: AskMessage;
  onOpenSource: (chunkId: string, claim: string) => void;
  onPreviewSource: (chunkId: string | null, claim: string) => void;
  pinnedChunkId: string | null;
  previewedChunkId: string | null;
}

const CitationRendererContext = React.createContext<CitationRenderContext | null>(null);

function chunkIdForCitation(message: AskMessage, number: number): string | undefined {
  return (
    message.citations?.find((citation) => citation.n === number)?.chunk_id ??
    message.retrieved?.find((passage) => passage.rank === number)?.chunk_id
  );
}

function renderCitations(
  node: ReactNode,
  message: AskMessage,
  onOpenSource: (chunkId: string, claim: string) => void,
  onPreviewSource: (chunkId: string | null, claim: string) => void,
  pinnedChunkId: string | null,
  previewedChunkId: string | null,
): ReactNode {
  if (typeof node === "string") {
    return node.split(/(\[\d+\])/g).map((part, index) => {
      const match = part.match(/^\[(\d+)\]$/);
      if (!match) return part;

      const number = Number(match[1]);
      return (
        <CitationChip
          key={`${number}-${index}`}
          n={number}
          citation={message.citations?.find((citation) => citation.n === number)}
          retrievedPassage={message.retrieved?.find((passage) => passage.rank === number)}
          onOpenSource={onOpenSource}
          onPreviewSource={onPreviewSource}
          claim={claimForCitation(message.content, number)}
          isPinned={pinnedChunkId === chunkIdForCitation(message, number)}
          isPreviewed={previewedChunkId === chunkIdForCitation(message, number)}
        />
      );
    });
  }

  if (Array.isArray(node)) {
    return node.map((child, index) => (
      <React.Fragment key={index}>
        {renderCitations(child, message, onOpenSource, onPreviewSource, pinnedChunkId, previewedChunkId)}
      </React.Fragment>
    ));
  }

  if (React.isValidElement<{ children?: ReactNode }>(node)) {
    return React.cloneElement(node, {
      children: renderCitations(
        node.props.children,
        message,
        onOpenSource,
        onPreviewSource,
        pinnedChunkId,
        previewedChunkId,
      ),
    });
  }

  return node;
}

function MarkdownParagraph({ children }: { children?: ReactNode }) {
  const context = useContext(CitationRendererContext);
  if (!context) return <p className="mb-3 leading-7">{children}</p>;

  return (
    <p className="mb-3 leading-7">
      {renderCitations(
        children,
        context.message,
        context.onOpenSource,
        context.onPreviewSource,
        context.pinnedChunkId,
        context.previewedChunkId,
      )}
    </p>
  );
}

function MarkdownListItem({ children }: { children?: ReactNode }) {
  const context = useContext(CitationRendererContext);
  if (!context) return <li>{children}</li>;

  return (
    <li>
      {renderCitations(
        children,
        context.message,
        context.onOpenSource,
        context.onPreviewSource,
        context.pinnedChunkId,
        context.previewedChunkId,
      )}
    </li>
  );
}

function MarkdownCode({ children }: { children?: ReactNode }) {
  return (
    <code className="rounded border border-line bg-surface-2 px-1.5 py-0.5 font-mono text-[13px]">
      {children}
    </code>
  );
}

function MarkdownPre({ children }: { children?: ReactNode }) {
  return (
    <pre className="my-2 overflow-x-auto rounded-ctrl border border-line bg-surface-2 p-3 font-mono text-xs">
      {children}
    </pre>
  );
}

const answerMarkdownComponents = {
  p: MarkdownParagraph,
  li: MarkdownListItem,
  code: MarkdownCode,
  pre: MarkdownPre,
};

export const AnswerMessage: React.FC<AnswerMessageProps> = ({
  message,
  question,
  onOpenSource,
  onPreviewSource,
  pinnedChunkId,
  previewedChunkId,
  isStreaming,
  hasScope,
  hasOtherCollections,
  onRegenerate,
  onPrefillQuestion,
  onAddLinkFocus,
  onSearchAllPages,
  onSwitchCollection,
}) => {
  const [copied, setCopied] = useState(false);
  const [copyError, setCopyError] = useState(false);

  const handleCopy = async () => {
    let exportText = message.content;
    if (message.citations?.length) {
      const sources = message.citations
        .map((citation) => `- [${citation.title}](${citation.url})`)
        .join("\n");
      exportText = `${exportText}\n\n${sources}`;
    }

    try {
      await navigator.clipboard.writeText(exportText);
      setCopyError(false);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1800);
    } catch {
      setCopyError(true);
    }
  };

  const hasInlineCitation = Boolean(message.citations?.length);
  const isVietnamese = /[ăâđêôơưàáạảãằắặẳẵầấậẩẫèéẹẻẽềếệểễìíịòóọỏõồốộổỗờớợởỡùúụủũừứựửữỳýỵỷỹ]/i.test(message.content);
  const visibleAnswer = message.content.replace(/\n\nStopped\.?$/, "");
  const originLabel = message.isNotFound
    ? strings.answerNotFound
    : hasInlineCitation
      ? strings.answerFromPages
      : strings.answerGeneral;

  return (
    <article className="my-8 space-y-4" aria-busy={isStreaming}>
      {question && (
        <div
          lang={/[ăâđêôơưàáạảãằắặẳẵầấậẩẫèéẹẻẽềếệểễìíịòóọỏõồốộổỗờớợởỡùúụủũừứựửữỳýỵỷỹ]/i.test(question) ? strings.textLanguageVietnamese : strings.textLanguageEnglish}
          className="w-full rounded-ctrl bg-surface-2 px-4 py-3"
        >
          <div className="mb-1 text-xs font-medium text-text-muted">
            {strings.questionLabel}
          </div>
          <p className="text-base font-semibold leading-6 text-text">{question}</p>
        </div>
      )}
      {copyError && <p role="alert" className="text-xs text-err">{strings.copyFailed}</p>}

      {message.isDemo && (
        <div className="inline-flex rounded-ctrl border border-warn/40 bg-warn/10 px-2.5 py-1 text-xs font-medium text-warn">
          {strings.demoData}
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span className={`inline-flex items-center gap-2 rounded-ctrl px-2.5 py-1 font-medium ${
          message.isNotFound ? "bg-warn/10 text-warn" : hasInlineCitation ? "bg-accent-soft text-accent" : "bg-surface-2 text-text-muted"
        }`}>
          <span className={`h-1.5 w-1.5 rounded-full ${
            message.isNotFound ? "bg-warn" : hasInlineCitation ? "bg-accent" : "bg-text-muted"
          }`} />
          {originLabel}
        </span>
      </div>
      {(message.stage || isStreaming) && (
        <ol className="flex flex-wrap gap-x-5 gap-y-1 text-xs" aria-label={strings.answerProgress}>
          {[strings.answerStepSearch, strings.answerStepRank, strings.answerStepWrite].map((step, index) => {
            const currentStage = message.stage ?? strings.answerStepWrite;
            const activeIndex = /rank|retriev/i.test(currentStage)
              ? 1
              : /writ|generat/i.test(currentStage)
                ? 2
                : 0;
            return (
              <li
                key={step}
                aria-current={index === activeIndex ? "step" : undefined}
                className={index === activeIndex ? "font-medium text-text" : "text-text-muted"}
              >
                {step}
              </li>
            );
          })}
        </ol>
      )}

      {message.isNotFound ? (
        <div className="space-y-3 rounded-pnl border border-line bg-surface p-4">
          <div className="flex items-center gap-2 text-base text-text">
            <span>{strings.notFoundHeadline}</span>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => onSearchAllPages?.(question ?? "")}
              hidden={!hasScope}
              className="min-h-10 rounded-ctrl border border-line bg-surface-2 px-3 text-sm text-text hover:bg-line"
            >
              {strings.searchAllPages}
            </button>
            {hasOtherCollections && (
              <button
                type="button"
                onClick={onSwitchCollection}
                className="min-h-10 rounded-ctrl border border-line bg-surface-2 px-3 text-sm text-text hover:bg-line"
              >
                {strings.switchCollection}
              </button>
            )}
            <button
              type="button"
              onClick={onAddLinkFocus}
              className="min-h-10 rounded-ctrl bg-accent px-3 text-sm text-accent-fg hover:opacity-90"
            >
              {strings.addPageAction}
            </button>
          </div>
        </div>
      ) : (
        <div
          lang={isVietnamese ? strings.textLanguageVietnamese : strings.textLanguageEnglish}
          className="space-y-3 font-sans text-base leading-7 text-text"
        >
          {visibleAnswer && (
            <CitationRendererContext.Provider
              value={{
                message,
                onOpenSource,
                onPreviewSource,
                pinnedChunkId,
                previewedChunkId,
              }}
            >
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={answerMarkdownComponents}
              >
                {visibleAnswer}
              </ReactMarkdown>
            </CitationRendererContext.Provider>
          )}
        </div>
      )}
      {visibleAnswer !== message.content && (
        <p className="text-sm text-text-muted">{strings.stopped}</p>
      )}

      {message.metrics && !message.stage && (
        <div className="flex items-center gap-2 text-xs text-text-muted">
          <Clock className="h-3.5 w-3.5" />
          <span>
            {strings.answerMetrics(message.metrics.passages_used, message.metrics.pages_used, message.metrics.duration)}
          </span>
        </div>
      )}
      {isStreaming && (
        <span className="inline-block h-4 w-1 animate-pulse bg-accent align-middle" aria-hidden="true" />
      )}
      {message.isError && question && (
        <button
          type="button"
          onClick={() => onPrefillQuestion?.(question)}
          className="min-h-9 rounded px-2 text-sm text-accent hover:bg-accent-soft"
        >
          {strings.tryAgain}
        </button>
      )}

      {!message.isNotFound && (
        <div className="flex items-center gap-2 border-t border-line/60 pt-2 text-xs text-text-muted">
          <button
            type="button"
            onClick={() => void handleCopy()}
            className="inline-flex min-h-9 items-center gap-1 rounded px-2 hover:bg-surface-2 hover:text-text"
            title={strings.copyAnswer}
          >
            {copied ? <Check className="h-3.5 w-3.5 text-ok" /> : <Copy className="h-3.5 w-3.5" />}
            {copied ? strings.copied : strings.copy}
          </button>
          {onRegenerate && (
            <button
              type="button"
              onClick={onRegenerate}
              className="inline-flex min-h-9 items-center gap-1 rounded px-2 hover:bg-surface-2 hover:text-text"
            >
              <RotateCw className="h-3.5 w-3.5" />
              {strings.regenerate}
            </button>
          )}
          {message.isError && question && (
            <button
              type="button"
              onClick={() => onPrefillQuestion?.(question)}
              className="min-h-9 rounded px-2 text-sm text-accent hover:bg-accent-soft"
            >
              {strings.tryAgain}
            </button>
          )}
        </div>
      )}
    </article>
  );
};
