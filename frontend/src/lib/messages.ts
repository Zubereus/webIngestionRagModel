import type { AskMessage } from "../api/types";

export function updateMessage(
  messages: AskMessage[],
  id: string,
  patch: Partial<AskMessage>,
): AskMessage[] {
  return messages.map((message) =>
    message.id === id ? { ...message, ...patch } : message,
  );
}
