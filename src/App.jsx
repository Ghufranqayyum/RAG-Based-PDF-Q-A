import { useEffect, useRef, useState } from "react";
import "./App.css";

const API = "http://localhost:8000";

export default function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [activeId, setActiveId] = useState(null);
  const [status, setStatus] = useState({ state: "checking", chunks: 0 });
  const endRef = useRef(null);

  useEffect(() => {
    fetch(`${API}/health`)
      .then((r) => r.json())
      .then((d) => setStatus({ state: "online", chunks: d.chunks }))
      .catch(() => setStatus({ state: "offline", chunks: 0 }));
  }, []);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function send() {
    const question = input.trim();
    if (!question || loading) return;

    setMessages((m) => [...m, { id: `u-${Date.now()}`, role: "user", text: question }]);
    setInput("");
    setLoading(true);

    const id = `a-${Date.now()}`;
    try {
      const res = await fetch(`${API}/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Something went wrong.");

      setMessages((m) => [...m, { id, role: "assistant", text: data.answer, sources: data.sources }]);
      setActiveId(id);
      setStatus((s) => ({ ...s, state: "online" }));
    } catch (err) {
      const offline = err instanceof TypeError;
      if (offline) setStatus({ state: "offline", chunks: 0 });
      setMessages((m) => [
        ...m,
        {
          id,
          role: "assistant",
          isError: true,
          sources: [],
          text: offline
            ? "Can’t reach the backend. Start it from the RAG folder with: uvicorn src.api:app --reload"
            : err.message,
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  function onKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  }

  const active = messages.find((m) => m.id === activeId);
  const sources = active?.sources ?? [];

  return (
    <div className="app">
      <section className="chat" aria-label="Chat">
        <header className="chat-head">
          <h1>Document Q&amp;A</h1>
          <p className={`status ${status.state}`}>
            {status.state === "online" && `${status.chunks} passages indexed`}
            {status.state === "offline" && "Backend offline"}
            {status.state === "checking" && "Connecting…"}
          </p>
        </header>

        <div className="thread">
          {messages.length === 0 && (
            <div className="empty">
              <p>Ask a question about your documents.</p>
              <p>Each answer names the file and page it came from.</p>
            </div>
          )}

          {messages.map((m) => (
            <article key={m.id} className={`msg ${m.role}${m.isError ? " error" : ""}`}>
              <p className="text">{m.text}</p>
              {m.role === "assistant" && m.sources?.length > 0 && (
                <button
                  className={`link ${m.id === activeId ? "on" : ""}`}
                  onClick={() => setActiveId(m.id)}
                >
                  {m.id === activeId ? "Showing sources" : `Show ${m.sources.length} sources`}
                </button>
              )}
            </article>
          ))}

          {loading && <p className="thinking">Searching documents…</p>}
          <div ref={endRef} />
        </div>

        <div className="composer">
          <textarea
            rows={2}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder="Type your question. Enter sends, Shift+Enter adds a line."
            aria-label="Your question"
          />
          <button onClick={send} disabled={loading || !input.trim()}>
            Ask
          </button>
        </div>
      </section>

      <aside className="sources" aria-label="Sources">
        <h2>Sources</h2>
        {sources.length === 0 ? (
          <p className="hint">The passages used for an answer appear here.</p>
        ) : (
          <ol>
            {sources.map((s, i) => (
              <li key={i}>
                <details open={i === 0}>
                  <summary>
                    <span className="file">{s.source}</span>
                    <span className="page">page {s.page}</span>
                  </summary>
                  <p>{s.text}</p>
                </details>
              </li>
            ))}
          </ol>
        )}
      </aside>
    </div>
  );
}