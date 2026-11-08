// TypeScript mirrors of the backend Pydantic schemas (docs/ARCHITECTURE.md section 5).
// Names and field shapes must match the backend exactly.

export type Mood = "calm" | "warm" | "happy" | "concerned" | "encouraging" | "serious";
export type Status = "draft" | "live" | "paused";
export type Industry = "astrology" | "general";
export type PrivacyMode = "A" | "B";

/** Shared character fields. Limits are enforced by the backend. */
export interface CharacterCard {
  name: string; // 1..80
  role: string; // <=200
  backstory: string; // <=2000
  speaking_style: string; // <=1000
  temperament: string; // <=200
  language: string; // <=40
  sample_lines: string[]; // <=10
  goals: string[]; // <=5, ordered
  rules: string[]; // <=30
}

/** Request body for creating a companion. Fields with backend defaults are optional. */
export interface CompanionCreate extends CharacterCard {
  industry?: Industry; // default "general"
  default_mood?: Mood; // default "calm"
  knowledge_tag_id?: string | null;
  privacy_mode?: PrivacyMode; // default "B"
  fallback_line?: string;
}

/** Request body for PATCH. Every field is optional. */
export type CompanionUpdate = Partial<CompanionCreate> & {
  status?: Status | null;
};

/** Response body for every companion route. */
export interface CompanionRead extends Required<CompanionCreate> {
  id: string;
  tenant_id: string;
  status: Status;
  created_at: string;
  updated_at: string;
}

/** Full set of values the character form edits. */
export type CompanionFormValues = Required<CompanionCreate>;

/** A tool the client app offers to the companion. */
export interface AppTool {
  name: string; // ^[a-z][a-z0-9_]{0,39}$
  description: string; // <=500
  parameters: Record<string, unknown>; // JSON schema, serialized <=4 KB
}

export interface TestChatRequest {
  message: string; // 1..8000
  display_name?: string | null;
  tools?: AppTool[]; // <=8
}

export interface ToolCall {
  id: string;
  name: string;
  args: Record<string, unknown>;
}

export interface ToolResult {
  id: string;
  output: unknown; // serialized output capped at 4000 chars by the backend
}

export interface ContinueRequest {
  turn_id: string;
  results: ToolResult[];
}

export interface CompanionReply {
  status: "done" | "tool_call";
  text: string | null;
  mood: Mood | null;
  conversation_id: string;
  message_id: string | null;
  turn_id: string | null;
  tool_calls: ToolCall[];
}

/** One item from GET /{id}/test-chat/history. `id` is always set; local items get a generated key. */
export interface HistoryMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  mood: Mood | null;
  created_at: string;
  /** Names and args only, never tool output. Present on messages where the companion asked for tools. */
  tool_calls?: { name: string; args: Record<string, unknown> }[] | null;
}

/** Error body returned for every domain error: {error, message}. */
export interface ErrorBody {
  error: string;
  message: string;
}
