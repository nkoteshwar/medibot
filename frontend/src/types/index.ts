export interface User {
  username: string;
  name: string;
  role: string;
  department: string;
  accessible_collections: string[];
  token?: string;
  is_analytical?: boolean;
}

export interface DemoUser {
  username: string;
  name: string;
  role: string;
  department: string;
  accessible_collections: string[];
  is_analytical: boolean;
  sample_password: string;
}

export interface SourceCitation {
  source_document: string;
  section_title: string;
  collection: string;
}

export interface RerankLog {
  initial_rank: number;
  new_rank: number;
  score: number;
  source_document: string;
  section_title: string;
  collection: string;
}

export interface Message {
  id: string;
  sender: "user" | "bot";
  text: string;
  timestamp: string;
  retrieval_type?: "hybrid_rag" | "sql_rag";
  sources?: SourceCitation[];
  sql_query?: string;
  access_blocked?: boolean;
  rerank_logs?: RerankLog[];
  role?: string;
}
