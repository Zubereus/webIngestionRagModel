import { useCallback, useRef, useState } from "react";
import type { AskMessage, Citation, RetrievedPassage } from "../api/types";
import { isMockMode, streamAsk } from "../api/client";
import { updateMessage } from "../lib/messages";
import { strings } from "../strings";

interface ConversationOptions {
  scope_doc_ids?: string[];
  collection: string;
  top_k: number;
  retrieval_mode: "hybrid" | "dense";
  model?: string;
}

function historyFromMessages(messages: AskMessage[]) {
  return messages
    .filter((message) => message.content.trim().length > 0)
    .slice(-6)
    .map((message) => ({
      role: message.role,
      content:
        message.role === "assistant"
          ? message.content.replace(/\[\d+\]/g, "")
          : message.content,
    }));
}

export function useConversation() {
  const [messages, setMessages] = useState<AskMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const stopStreamingRef = useRef<(() => void) | null>(null);

  const patchMessage = useCallback(
    (
      id: string,
      patch:
        | Partial<AskMessage>
        | ((message: AskMessage) => Partial<AskMessage>),
    ) => {
      setMessages((currentMessages) => {
        const message = currentMessages.find((item) => item.id === id);
        if (!message) return currentMessages;
        const resolvedPatch = typeof patch === "function" ? patch(message) : patch;
        return updateMessage(currentMessages, id, resolvedPatch);
      });
    },
    [],
  );

  const sendQuestion = useCallback(
    (question: string, options: ConversationOptions) => {
      const userMessage: AskMessage = {
        id: crypto.randomUUID(),
        role: "user",
        content: question,
        timestamp: new Date().toISOString(),
      };
      const assistantId = crypto.randomUUID();
      const assistantMessage: AskMessage = {
        id: assistantId,
        role: "assistant",
        content: "",
        timestamp: new Date().toISOString(),
        stage: "Searching your pages",
        isDemo: isMockMode(),
      };

      setMessages((currentMessages) => [
        ...currentMessages,
        userMessage,
        assistantMessage,
      ]);
      setIsStreaming(true);

      const stop = streamAsk(
        question,
        {
          onStage: (stage) => patchMessage(assistantId, { stage }),
          onToken: (token) =>
            patchMessage(assistantId, (message) => ({
              content: message.content + token,
              stage: undefined,
            })),
          onCitations: (citations: Citation[]) =>
            patchMessage(assistantId, { citations }),
          onRetrieved: (retrieved: RetrievedPassage[]) =>
            patchMessage(assistantId, { retrieved }),
          onNotFound: () =>
            patchMessage(assistantId, {
              isNotFound: true,
              stage: undefined,
              content: "",
              citations: [],
              retrieved: [],
            }),
          onDone: (metrics) => {
            patchMessage(assistantId, { metrics, stage: undefined });
            setIsStreaming(false);
            stopStreamingRef.current = null;
          },
          onError: (error) => {
            patchMessage(assistantId, (message) => ({
              content: `${message.content}\n\n*Error:* ${error}`,
              stage: undefined,
              isError: true,
            }));
            setIsStreaming(false);
            stopStreamingRef.current = null;
          },
        },
        {
          ...options,
          history: historyFromMessages(messages),
        },
      );

      stopStreamingRef.current = stop;
    },
    [messages, patchMessage],
  );

  const stop = () => {
    stopStreamingRef.current?.();
    stopStreamingRef.current = null;
    setMessages((currentMessages) => {
      const assistant = [...currentMessages]
        .reverse()
        .find((message) => message.role === "assistant");
      if (!assistant) return currentMessages;
      const content = assistant.content.trim();
      return updateMessage(currentMessages, assistant.id, {
        content: content
          ? `${content}\n\n${strings.stopped}`
          : strings.stopped,
        stage: undefined,
      });
    });
    setIsStreaming(false);
  };

  const clear = () => {
    stopStreamingRef.current?.();
    stopStreamingRef.current = null;
    setIsStreaming(false);
    setMessages([]);
  };

  return { messages, isStreaming, sendQuestion, stop, clear };
}
