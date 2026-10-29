export type PageStatus = "queued" | "fetching" | "extracting" | "indexing" | "ready" | "failed";

export interface BackendHealth {
  status: string;
  model?: string;
  embed_model?: string;
}

export interface GenerationModel {
  id: string;
  label: string;
  provider: "ollama" | "gemini";
  available: boolean;
}

export interface Page {
  doc_id: string;
  canonical_url: string;
  domain: string;
  title: string;
  language: string | null;
  fetched_at: string;
  chunk_count: number;
  status: PageStatus;
  collection: string;
  error?: string;
  duplicate?: boolean;
}

export interface Chunk {
  chunk_id: string;
  doc_id: string;
  ordinal: number;
  text: string;
  section_path: string[];
  url: string;
  title: string;
  fetched_at: string;
  context_before?: string;
  context_after?: string;
}

export interface Citation {
  n: number;
  chunk_id: string;
  doc_id: string;
  title: string;
  url: string;
  score: number;
}

export interface RetrievedPassage {
  rank: number;
  score: number;
  dense_score?: number;
  bm25_score?: number;
  title: string;
  url: string;
  snippet: string;
  chunk_id: string;
}

export interface AskMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
  stage?: string;
  citations?: Citation[];
  retrieved?: RetrievedPassage[];
  metrics?: {
    duration: number;
    passages_used: number;
    pages_used: number;
  };
  isNotFound?: boolean;
  isDemo?: boolean;
  isError?: boolean;
}
