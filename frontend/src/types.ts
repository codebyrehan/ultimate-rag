export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
  full_name?: string;
  tenant_name: string;
}

export interface LoginRequest {
  email: string;
  password: string;
  tenant_name: string;
}

export interface ChatRequest {
  query: string;
  conversation_id?: string | null;
}

export interface ChatResponse {
  query_id: string;
  conversation_id?: string | null;
  answer: string;
  confidence: number;
  model: string;
  citations: Citation[];
}

export interface Citation {
  chunk_id: string;
  label: string;
  score: number;
  doc_filename: string;
  page_number: number;
  verified: boolean;
  supported_fraction: number;
}

export interface DocumentResponse {
  id: string;
  filename: string;
  original_filename: string;
  page_count: number;
  sha256: string;
  version: number;
  status: string;
  indexing_status: string;
  created_at?: string | null;
  chunks: ChunkInfo[];
}

export interface ChunkInfo {
  id: string;
  page_number: number;
  section?: string | null;
}

export interface ConversationResponse {
  id: string;
  title?: string | null;
  created_at: string;
  updated_at: string;
  messages: MessageInfo[];
}

export interface MessageInfo {
  id: string;
  role: string;
  content: string;
  created_at: string;
}

export interface JobResponse {
  id: string;
  kind: string;
  status: string;
  created_at: string;
  started_at?: string | null;
  finished_at?: string | null;
  error?: string | null;
  result?: Record<string, unknown> | null;
}

export interface StreamEvent {
  type: 'token' | 'done';
  data?: string;
  citations?: Citation[];
  confidence?: number;
  model?: string;
  query_id?: string;
  conversation_id?: string;
}
