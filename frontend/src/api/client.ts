import type {
  BackendHealth,
  Chunk,
  Citation,
  GenerationModel,
  Page,
  RetrievedPassage,
} from "./types";
import { MOCK_CHUNKS, MOCK_PAGES } from "./mockData";

export const DEFAULT_API_URL = typeof window !== "undefined" ? window.location.origin : "http://localhost:8000";

let currentBaseUrl = localStorage.getItem("webrag_api_url") || DEFAULT_API_URL;
let mockMode =
  import.meta.env.DEV && localStorage.getItem("webrag_mock_mode") === "true";
let mockCollections = Array.from(
  new Set(MOCK_PAGES.map((page) => page.collection).concat("default")),
);

export const getApiBaseUrl = () => currentBaseUrl;
export const setApiBaseUrl = (url: string) => {
  currentBaseUrl = url;
  localStorage.setItem("webrag_api_url", url);
};
export const getSelectedModel = () => localStorage.getItem("webrag_model");
export const setSelectedModel = (model: string) => {
  localStorage.setItem("webrag_model", model);
};

export const isMockMode = () => mockMode;
export const setMockMode = (active: boolean) => {
  mockMode = import.meta.env.DEV && active;
  localStorage.setItem("webrag_mock_mode", mockMode ? "true" : "false");
  mockCollections = Array.from(
    new Set(MOCK_PAGES.map((page) => page.collection).concat("default")),
  );
};

export async function fetchCollections(): Promise<string[]> {
  if (mockMode) return [...mockCollections];

  const res = await fetch(`${currentBaseUrl}/api/collections`);
  if (!res.ok) {
    throw new Error(`Failed to load collections (HTTP ${res.status}).`);
  }
  const data: unknown = await res.json();
  if (
    typeof data !== "object" ||
    data === null ||
    !("collections" in data) ||
    !Array.isArray(data.collections) ||
    !data.collections.every((name) => typeof name === "string")
  ) {
    throw new Error("The collections response was invalid.");
  }
  return data.collections;
}

export async function createCollection(name: string): Promise<string> {
  if (mockMode) {
    const trimmedName = name.trim();
    const normalizedName = trimmedName.replace(/[ -]+/g, "_").toLowerCase();
    if (!/^[a-z0-9](?:[a-z0-9 _-]{1,61}[a-z0-9])$/i.test(trimmedName)) {
      throw new Error(
        "Collection names must be 3–63 characters, start and end with a letter or number, and contain only letters, numbers, spaces, hyphens, or underscores.",
      );
    }
    if (mockCollections.includes(normalizedName)) {
      throw new Error("This collection already exists.");
    }
    mockCollections = [...mockCollections, normalizedName].sort();
    return normalizedName;
  }

  const res = await fetch(`${currentBaseUrl}/api/collections`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || `Failed to create collection (HTTP ${res.status}).`);
  }
  const data: unknown = await res.json();
  if (typeof data !== "object" || data === null || !("name" in data) || typeof data.name !== "string") {
    throw new Error("The created collection response was invalid.");
  }
  return data.name;
}

export async function checkBackendHealth(): Promise<boolean> {
  return (await fetchBackendHealth()) !== null;
}

export async function fetchBackendHealth(): Promise<BackendHealth | null> {
  if (mockMode) return null;
  try {
    const res = await fetch(`${currentBaseUrl}/api/health`, {
      method: "GET",
      signal: AbortSignal.timeout(2500),
    });
    if (!res.ok) return null;
    const health: unknown = await res.json();
    if (
      typeof health !== "object" ||
      health === null ||
      !("status" in health) ||
      typeof health.status !== "string"
    ) {
      return null;
    }
    return {
      status: health.status,
      model: "model" in health && typeof health.model === "string" ? health.model : undefined,
      embed_model:
        "embed_model" in health && typeof health.embed_model === "string"
          ? health.embed_model
          : undefined,
    };
  } catch {
    return null;
  }
}

export async function fetchGenerationModels(): Promise<{
  default_model: string;
  models: GenerationModel[];
}> {
  if (mockMode) {
    return {
      default_model: "gemini-3.5-flash",
      models: [
        { id: "qwen2.5:1.5b", label: "Qwen 2.5 · 1.5B", provider: "ollama", available: true },
        { id: "qwen2.5:3b", label: "Qwen 2.5 · 3B", provider: "ollama", available: true },
        { id: "qwen2.5:7b", label: "Qwen 2.5 · 7B", provider: "ollama", available: true },
        { id: "qwen3:4b", label: "Qwen 3 · 4B", provider: "ollama", available: true },
        { id: "gemini-2.5-flash", label: "Gemini 2.5 Flash", provider: "gemini", available: false },
        { id: "gemini-3.5-flash", label: "Gemini 3.5 Flash", provider: "gemini", available: true },
      ],
    };
  }

  const res = await fetch(`${currentBaseUrl}/api/models`);
  if (!res.ok) {
    throw new Error(`Failed to load models (HTTP ${res.status}).`);
  }
  const data: unknown = await res.json();
  const isGenerationModel = (value: unknown): value is GenerationModel =>
    typeof value === "object" &&
    value !== null &&
    "id" in value &&
    typeof value.id === "string" &&
    "label" in value &&
    typeof value.label === "string" &&
    "provider" in value &&
    (value.provider === "ollama" || value.provider === "gemini") &&
    "available" in value &&
    typeof value.available === "boolean";
  if (
    typeof data !== "object" ||
    data === null ||
    !("default_model" in data) ||
    typeof data.default_model !== "string" ||
    !("models" in data) ||
    !Array.isArray(data.models) ||
    !data.models.every(isGenerationModel)
  ) {
    throw new Error("The models response was invalid.");
  }
  return { default_model: data.default_model, models: data.models };
}

export async function fetchPages(params?: { status?: string; domain?: string; q?: string; collection?: string }): Promise<Page[]> {
  if (mockMode) {
    let pages = [...MOCK_PAGES];
    if (params?.status && params.status !== "all") {
      pages = pages.filter((p) => p.status === params.status);
    }
    if (params?.domain) {
      pages = pages.filter((p) => p.domain.toLowerCase().includes(params.domain!.toLowerCase()));
    }
    if (params?.q) {
      pages = pages.filter(
        (p) =>
          p.title.toLowerCase().includes(params.q!.toLowerCase()) ||
          p.canonical_url.toLowerCase().includes(params.q!.toLowerCase())
      );
    }
    return pages;
  }

  const query = new URLSearchParams();
  if (params?.status && params.status !== "all") query.set("status", params.status);
  if (params?.domain) query.set("domain", params.domain);
  if (params?.q) query.set("q", params.q);
  if (params?.collection) query.set("collection", params.collection);

  const res = await fetch(`${currentBaseUrl}/api/pages?${query.toString()}`);
  if (!res.ok) throw new Error(`Failed to load pages (HTTP ${res.status}).`);
  return await res.json();
}

export async function clearLibrary(): Promise<void> {
  if (mockMode) return;
  const res = await fetch(`${currentBaseUrl}/api/library/clear`, {
    method: "DELETE",
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || `Failed to clear library (HTTP ${res.status}).`);
  }
}

interface PageEventCallbacks {
  onConnectionChange: (connected: boolean) => void;
  onPageEvent: (event: "stage" | "ready" | "failed", data: unknown) => void;
}

export function subscribePageEvents(callbacks: PageEventCallbacks): () => void {
  if (mockMode || typeof EventSource === "undefined") {
    callbacks.onConnectionChange(false);
    return () => {};
  }

  const eventSource = new EventSource(`${currentBaseUrl}/api/pages/events`);
  eventSource.onopen = () => callbacks.onConnectionChange(true);
  eventSource.onerror = () => callbacks.onConnectionChange(false);

  const handlePageEvent = (event: MessageEvent<string>) => {
    callbacks.onPageEvent("stage", event.data);
  };
  const handleReadyEvent = (event: MessageEvent<string>) => {
    callbacks.onPageEvent("ready", event.data);
  };
  const handleFailedEvent = (event: MessageEvent<string>) => {
    callbacks.onPageEvent("failed", event.data);
  };

  eventSource.addEventListener("stage", handlePageEvent);
  eventSource.addEventListener("ready", handleReadyEvent);
  eventSource.addEventListener("failed", handleFailedEvent);

  return () => {
    eventSource.close();
    callbacks.onConnectionChange(false);
  };
}

export async function addPage(url: string, collection: string = "default"): Promise<Page> {
  if (mockMode) {
    const doc_id = Math.random().toString(16).slice(2, 10);
    const domain = new URL(url).hostname;
    const newPage: Page = {
      doc_id,
      canonical_url: url,
      domain,
      title: url,
      language: "en",
      fetched_at: new Date().toISOString(),
      chunk_count: 5,
      status: "queued",
      collection,
    };
    return newPage;
  }

  const res = await fetch(`${currentBaseUrl}/api/pages`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url, collection }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || `HTTP ${res.status}`);
  }
  return await res.json();
}

export async function refetchPage(doc_id: string): Promise<void> {
  if (mockMode) return;
  const res = await fetch(`${currentBaseUrl}/api/pages/${doc_id}/refetch`, {
    method: "POST",
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || `Failed to refetch page (HTTP ${res.status}).`);
  }
}

export async function deletePage(doc_id: string): Promise<void> {
  if (mockMode) return;
  const res = await fetch(`${currentBaseUrl}/api/pages/${doc_id}`, { method: "DELETE" });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || `HTTP ${res.status}`);
  }
}

export async function fetchChunk(chunk_id: string): Promise<Chunk> {
  if (mockMode || MOCK_CHUNKS[chunk_id]) {
    return (
      MOCK_CHUNKS[chunk_id] || {
        chunk_id,
        doc_id: chunk_id.split(":")[0],
        ordinal: 0,
        text: "Sample chunk content rendered in mock mode.",
        section_path: ["Overview"],
        url: "https://example.com",
        title: "Sample Document",
        fetched_at: new Date().toISOString(),
        context_before: "Preceding section text...",
        context_after: "Subsequent section text...",
      }
    );
  }

  const res = await fetch(`${currentBaseUrl}/api/chunks/${chunk_id}`);
  if (!res.ok) throw new Error("Chunk not found");
  return await res.json();
}

export async function fetchPageDetails(doc_id: string): Promise<any> {
  if (mockMode) {
    return {
      doc_id,
      title: "Sample Article",
      markdown: "# Sample Article\n\nThis is a sample document extracted from the web.",
      canonical_url: "https://example.com",
    };
  }
  const res = await fetch(`${currentBaseUrl}/api/pages/${doc_id}`);
  if (!res.ok) throw new Error("Page not found");
  return await res.json();
}

export interface StreamAskCallbacks {
  onStage?: (stage: string) => void;
  onToken?: (token: string) => void;
  onCitations?: (citations: Citation[]) => void;
  onRetrieved?: (passages: RetrievedPassage[]) => void;
  onNotFound?: (message: string) => void;
  onDone?: (metrics: AskMetrics) => void;
  onError?: (error: string) => void;
}

export interface AskMetrics {
  duration: number;
  passages_used: number;
  pages_used: number;
}

export interface ConversationHistoryItem {
  role: "user" | "assistant";
  content: string;
}

export function streamAsk(
  question: string,
  callbacks: StreamAskCallbacks,
  options?: {
    scope_doc_ids?: string[];
    collection?: string;
    top_k?: number;
    retrieval_mode?: "hybrid" | "dense";
    history?: ConversationHistoryItem[];
    model?: string;
    signal?: AbortSignal;
  }
) {
  if (mockMode) {
    // Simulate realistic SSE streaming in mock mode
    let aborted = false;
    options?.signal?.addEventListener("abort", () => {
      aborted = true;
    });

    const runMock = async () => {
      callbacks.onStage?.("Searching your pages");
      await new Promise((r) => setTimeout(r, 400));
      if (aborted) return;

      callbacks.onStage?.("Ranking passages");
      await new Promise((r) => setTimeout(r, 400));
      if (aborted) return;

      const isVi = question.toLowerCase().includes("việt") || question.toLowerCase().includes("tìm kiếm");

      const mockCitations: Citation[] = isVi
        ? [
            {
              n: 1,
              chunk_id: "c88f12a03e1b4231:0",
              doc_id: "c88f12a03e1b4231",
              title: "Ứng dụng tìm kiếm thông tin thông minh trong kỷ nguyên AI",
              url: "https://vnexpress.net/ung-dung-tim-kiem-thong-tin-thong-minh-trong-ky-nguyen-ai",
              score: 0.94,
            },
          ]
        : [
            {
              n: 1,
              chunk_id: "b43f8e16786a1aa9:1",
              doc_id: "b43f8e16786a1aa9",
              title: "Retrieval-augmented generation - Wikipedia",
              url: "https://en.wikipedia.org/wiki/Retrieval-augmented_generation",
              score: 0.92,
            },
            {
              n: 2,
              chunk_id: "94c74a9258b3dd5f:2",
              doc_id: "94c74a9258b3dd5f",
              title: "First Steps - FastAPI Tutorial",
              url: "https://fastapi.tiangolo.com/tutorial/first-steps",
              score: 0.88,
            },
          ];

      const mockRetrieved: RetrievedPassage[] = isVi
        ? [
            {
              rank: 1,
              score: 0.94,
              title: "Ứng dụng tìm kiếm thông tin thông minh trong kỷ nguyên AI",
              url: "https://vnexpress.net/ung-dung-tim-kiem-thong-tin-thong-minh-trong-ky-nguyen-ai",
              snippet: "Ứng dụng tìm kiếm thông tin tăng cường (RAG) giúp loại bỏ hiện tượng ảo giác trong các mô hình ngôn ngữ lớn...",
              chunk_id: "c88f12a03e1b4231:0",
            },
          ]
        : [
            {
              rank: 1,
              score: 0.92,
              title: "Retrieval-augmented generation - Wikipedia",
              url: "https://en.wikipedia.org/wiki/Retrieval-augmented_generation",
              snippet: "The term retrieval-augmented generation (RAG) was introduced in a 2020 paper by Patrick Lewis...",
              chunk_id: "b43f8e16786a1aa9:1",
            },
            {
              rank: 2,
              score: 0.88,
              title: "First Steps - FastAPI Tutorial",
              url: "https://fastapi.tiangolo.com/tutorial/first-steps",
              snippet: "Import FastAPI and create an app instance using app = FastAPI(). Then write a path operation decorator...",
              chunk_id: "94c74a9258b3dd5f:2",
            },
          ];

      callbacks.onCitations?.(mockCitations);
      callbacks.onRetrieved?.(mockRetrieved);

      callbacks.onStage?.("Writing answer");
      await new Promise((r) => setTimeout(r, 300));
      if (aborted) return;

      const answerText = isVi
        ? "Mô hình tìm kiếm tăng cường (RAG) cho phép các hệ thống AI truy xuất và trích dẫn thông tin chính xác từ tài liệu nguồn [1]. Phương pháp này giúp khắc phục nhược điểm thông tin sai lệch (hallucination) và mang lại sự tin cậy cao cho người dùng [1]."
        : "Retrieval-augmented generation (RAG) combines a parametric neural language model with non-parametric retrieval memory [1]. In Python web frameworks like FastAPI, you can quickly build an API endpoint to serve these models by creating an `app = FastAPI()` instance and adding path operation decorators [2].";

      // Stream words
      const words = answerText.split(" ");
      for (const word of words) {
        if (aborted) return;
        callbacks.onToken?.(word + " ");
        await new Promise((r) => setTimeout(r, 45));
      }

      callbacks.onDone?.({ duration: 1.8, passages_used: mockCitations.length, pages_used: mockCitations.length });
    };

    runMock();
    return () => {
      aborted = true;
    };
  }

  // Live SSE stream to FastAPI
  const controller = new AbortController();
  const signal = options?.signal || controller.signal;

  (async () => {
    try {
      const response = await fetch(`${currentBaseUrl}/api/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question,
          scope_doc_ids: options?.scope_doc_ids,
          collection: options?.collection || "default",
          top_k: options?.top_k || 5,
          retrieval_mode: options?.retrieval_mode || "hybrid",
          history: options?.history || [],
          model: options?.model,
        }),
        signal,
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error("No readable stream");

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n\n");
        buffer = lines.pop() || "";

        for (const block of lines) {
          if (!block.trim()) continue;
          let eventType = "message";
          let dataText = "";

          for (const line of block.split("\n")) {
            if (line.startsWith("event: ")) {
              eventType = line.slice(7).trim();
            } else if (line.startsWith("data: ")) {
              dataText = line.slice(6).trim();
            }
          }

          if (dataText) {
            try {
              const data = JSON.parse(dataText);
              if (eventType === "stage") callbacks.onStage?.(data.name);
              else if (eventType === "token") callbacks.onToken?.(data.text);
              else if (eventType === "citations") callbacks.onCitations?.(data);
              else if (eventType === "retrieved") callbacks.onRetrieved?.(data);
              else if (eventType === "not_found") callbacks.onNotFound?.(data.message);
              else if (eventType === "done") callbacks.onDone?.(data);
              else if (eventType === "error") callbacks.onError?.(data.message);
            } catch (err) {
              console.error("Failed to parse SSE payload:", err, dataText);
            }
          }
        }
      }
    } catch (err: any) {
      if (err.name !== "AbortError") {
        callbacks.onError?.(err.message || "Failed to communicate with backend");
      }
    }
  })();

  return () => {
    controller.abort();
  };
}
