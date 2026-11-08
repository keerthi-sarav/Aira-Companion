"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { ApiError, api, errorText, testExternalUserId } from "@/lib/api";
import type { AppTool, CompanionReply, HistoryMessage, ToolCall, ToolResult } from "@/lib/types";
import MoodBadge from "./MoodBadge";

const TOOL_NAME_RE = /^[a-z][a-z0-9_]{0,39}$/;
const MAX_TOOLS = 8;
const MAX_PARAMS_BYTES = 4096;

const SAMPLE_TOOLS: AppTool[] = [
  {
    name: "get_chart",
    description: "Returns the birth chart for the given date, time and place.",
    parameters: {
      type: "object",
      properties: {
        date: { type: "string", description: "Birth date, YYYY-MM-DD" },
        time: { type: "string", description: "Birth time, HH:MM (24h)" },
        place: { type: "string", description: "Birth place, city and country" },
      },
      required: ["date", "time", "place"],
    },
  },
];

const DEFAULT_TOOLS_JSON = JSON.stringify(SAMPLE_TOOLS, null, 2);

/** Parses and checks the tools editor text. Throws an Error with a readable message. */
function parseTools(text: string): AppTool[] {
  let data: unknown;
  try {
    data = JSON.parse(text);
  } catch {
    throw new Error("Tools JSON is not valid JSON.");
  }
  if (!Array.isArray(data)) {
    throw new Error("Tools must be a JSON array.");
  }
  if (data.length > MAX_TOOLS) {
    throw new Error(`At most ${MAX_TOOLS} tools.`);
  }
  for (let i = 0; i < data.length; i += 1) {
    const label = `Tool ${i + 1}`;
    const tool = data[i];
    if (typeof tool !== "object" || tool === null || Array.isArray(tool)) {
      throw new Error(`${label} must be an object.`);
    }
    const t = tool as Record<string, unknown>;
    if (typeof t.name !== "string" || !TOOL_NAME_RE.test(t.name)) {
      throw new Error(`${label}: name must start with a lowercase letter, use only a-z, 0-9 and _, and be at most 40 characters.`);
    }
    if (typeof t.description !== "string" || t.description.length > 500) {
      throw new Error(`${label}: description must be text, at most 500 characters.`);
    }
    if (typeof t.parameters !== "object" || t.parameters === null || Array.isArray(t.parameters)) {
      throw new Error(`${label}: parameters must be a JSON schema object.`);
    }
    const bytes = new TextEncoder().encode(JSON.stringify(t.parameters)).length;
    if (bytes > MAX_PARAMS_BYTES) {
      throw new Error(`${label}: parameters are larger than 4 KB.`);
    }
  }
  return data as AppTool[];
}

interface PendingTurn {
  turnId: string;
  calls: ToolCall[];
  outputs: Record<string, string>; // call id -> JSON text typed by the user
}

/** Generated key for a message that has no server id yet. Never collides with a server id. */
function newLocalKey(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return `local-${crypto.randomUUID()}`;
  }
  return `local-${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
}

function makeItem(
  role: "user" | "assistant",
  content: string,
  mood: HistoryMessage["mood"] = null,
  id?: string,
): HistoryMessage {
  return {
    id: id ?? newLocalKey(),
    role,
    content,
    mood,
    created_at: new Date().toISOString(),
  };
}

/** Keeps the first item for each id so every rendered key is unique. */
function uniqueById(items: HistoryMessage[]): HistoryMessage[] {
  const seen = new Set<string>();
  return items.filter((item) => {
    if (seen.has(item.id)) return false;
    seen.add(item.id);
    return true;
  });
}

export default function TestChat({ companionId }: { companionId: string }) {
  const [messages, setMessages] = useState<HistoryMessage[]>([]);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [pending, setPending] = useState<PendingTurn | null>(null);
  const [toolsText, setToolsText] = useState(DEFAULT_TOOLS_JSON);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const listRef = useRef<HTMLDivElement>(null);

  // Load history whenever the companion changes.
  useEffect(() => {
    let cancelled = false;
    setHistoryLoading(true);
    setMessages([]);
    setPending(null);
    setError(null);
    setNotice(null);
    api
      .getTestChatHistory(companionId)
      .then((items) => {
        if (!cancelled) setMessages(uniqueById(items));
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(errorText(err));
      })
      .finally(() => {
        if (!cancelled) setHistoryLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [companionId]);

  // Keep the newest message in view, scrolling only the chat box.
  useEffect(() => {
    const el = listRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages, pending, historyLoading]);

  function applyReply(reply: CompanionReply) {
    if (reply.text) {
      const item = makeItem("assistant", reply.text, reply.mood, reply.message_id ?? undefined);
      setMessages((prev) => [...prev.filter((m) => m.id !== item.id), item]);
    }
    if (reply.status === "tool_call" && reply.turn_id) {
      setPending({
        turnId: reply.turn_id,
        calls: reply.tool_calls,
        outputs: Object.fromEntries(reply.tool_calls.map((call) => [call.id, "{}"])),
      });
    } else {
      setPending(null);
    }
  }

  async function send(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = draft.trim();
    // Not while history loads: the history response replaces the list, which would drop this message.
    if (!text || sending || pending || historyLoading) return;

    let tools: AppTool[];
    try {
      tools = parseTools(toolsText);
    } catch (err) {
      setError(errorText(err));
      return;
    }

    const userItem = makeItem("user", text);
    setDraft("");
    setError(null);
    setNotice(null);
    setSending(true);
    setMessages((prev) => [...prev, userItem]);
    try {
      const reply = await api.testChat(companionId, { message: text, tools });
      applyReply(reply);
    } catch (err) {
      // The message was not saved, so take it back out and restore the draft.
      setMessages((prev) => prev.filter((m) => m.id !== userItem.id));
      setDraft(text);
      setError(errorText(err));
    } finally {
      setSending(false);
    }
  }

  async function sendResults() {
    if (!pending || sending) return;

    let results: ToolResult[];
    try {
      results = pending.calls.map((call) => {
        const raw = pending.outputs[call.id] ?? "";
        try {
          return { id: call.id, output: JSON.parse(raw) as unknown };
        } catch {
          throw new Error(`Output for ${call.name} is not valid JSON.`);
        }
      });
    } catch (err) {
      setError(errorText(err));
      return;
    }

    setError(null);
    setNotice(null);
    setSending(true);
    try {
      const reply = await api.continueTestChat({ turn_id: pending.turnId, results });
      applyReply(reply);
    } catch (err) {
      setError(errorText(err));
      if (err instanceof ApiError && err.error === "turn_expired") {
        setPending(null);
      }
    } finally {
      setSending(false);
    }
  }

  async function forgetTestUser() {
    if (!window.confirm("Forget the test user? This deletes their messages across all characters of this tenant.")) {
      return;
    }
    setError(null);
    setNotice(null);
    try {
      await api.forgetEndUser(testExternalUserId);
      setMessages([]);
      setPending(null);
      setNotice("Test user forgotten. The next message starts fresh.");
    } catch (err) {
      setError(errorText(err));
    }
  }

  const waiting = pending !== null;

  return (
    <section className="card flex flex-col gap-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="section-title">Test chat</h2>
          <p className="hint">Chatting as {testExternalUserId}</p>
        </div>
        <button type="button" className="btn btn-danger" onClick={forgetTestUser} disabled={sending}>
          Forget me
        </button>
      </div>

      <div
        ref={listRef}
        className="flex h-[26rem] flex-col gap-3 overflow-y-auto rounded-lg bg-neutral-50 p-3"
      >
        {historyLoading ? (
          <p className="text-sm text-neutral-500">Loading history...</p>
        ) : messages.length === 0 && !waiting ? (
          <p className="m-auto text-center text-sm text-neutral-500">
            No messages yet. Send a message to test this character.
          </p>
        ) : null}

        {messages.map((m) => (
          <div key={m.id} className={m.role === "user" ? "flex justify-end" : "flex justify-start"}>
            <div
              className={`max-w-[80%] whitespace-pre-wrap break-words rounded-2xl px-3 py-2 text-sm ${
                m.role === "user"
                  ? "bg-neutral-900 text-white"
                  : "bg-white text-neutral-900 ring-1 ring-neutral-200"
              }`}
            >
              {m.content}
              {m.role === "assistant" && m.mood ? (
                <div className="mt-2">
                  <MoodBadge mood={m.mood} />
                </div>
              ) : null}
            </div>
          </div>
        ))}

        {pending ? (
          <div className="space-y-3 rounded-lg border border-amber-300 bg-amber-50 p-3">
            <p className="text-sm font-medium text-amber-900">
              The companion asked for {pending.calls.length === 1 ? "a tool" : `${pending.calls.length} tools`}.
              Run {pending.calls.length === 1 ? "it" : "them"} in your app and paste the output as JSON.
            </p>
            {pending.calls.map((call) => (
              <div key={call.id} className="space-y-2">
                <div className="text-xs text-neutral-700">
                  <span className="font-mono font-semibold">{call.name}</span>
                  <pre className="mt-1 overflow-x-auto rounded bg-white p-2 font-mono text-xs">
                    {JSON.stringify(call.args, null, 2)}
                  </pre>
                </div>
                <label htmlFor={`out-${call.id}`} className="label">
                  Output for {call.name} (JSON)
                </label>
                <textarea
                  id={`out-${call.id}`}
                  rows={4}
                  spellCheck={false}
                  className="input font-mono text-xs"
                  value={pending.outputs[call.id] ?? ""}
                  onChange={(e) => {
                    const value = e.target.value;
                    setPending((p) => (p ? { ...p, outputs: { ...p.outputs, [call.id]: value } } : p));
                  }}
                />
              </div>
            ))}
            <div className="flex gap-2">
              <button type="button" className="btn btn-primary" onClick={sendResults} disabled={sending}>
                Send result
              </button>
              <button type="button" className="btn" onClick={() => setPending(null)} disabled={sending}>
                Discard
              </button>
            </div>
          </div>
        ) : null}
      </div>

      {error ? (
        <div role="alert" className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </div>
      ) : null}
      {notice ? (
        <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
          {notice}
        </div>
      ) : null}

      <details className="rounded-lg border border-neutral-200 bg-white p-3 text-sm">
        <summary className="cursor-pointer font-medium text-neutral-700">Tools (JSON)</summary>
        <div className="mt-3 space-y-2">
          <textarea
            aria-label="Tools JSON"
            rows={12}
            spellCheck={false}
            className="input font-mono text-xs"
            value={toolsText}
            onChange={(e) => setToolsText(e.target.value)}
          />
          <div className="flex flex-wrap items-center gap-2">
            <button type="button" className="btn" onClick={() => setToolsText(DEFAULT_TOOLS_JSON)}>
              Reset to sample
            </button>
            <span className="hint">Up to 8 tools, sent with each message. An empty array [] turns tools off.</span>
          </div>
        </div>
      </details>

      <form onSubmit={send} className="flex gap-2">
        <input
          type="text"
          aria-label="Message"
          maxLength={8000}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          disabled={sending || waiting || historyLoading}
          placeholder={waiting ? "Send the tool result first" : "Type a message"}
          className="input"
        />
        <button
          type="submit"
          className="btn btn-primary"
          disabled={sending || waiting || historyLoading || draft.trim() === ""}
        >
          Send
        </button>
      </form>
    </section>
  );
}
