
import { useEffect, useRef, useState } from "react";
import ChatbotIcon from "./components/ChatbotIcon";
import ChatForm from "./components/ChatForm";
import ChatMessage from "./components/ChatMessage";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

const SUGGESTIONS = [
  "Show me all the products",
  "Which suppliers provide furniture?",
  "Which is the least priced product?",
  "Which supplier sells the most products?",
];

const App = () => {
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [showChatbot, setShowChatbot] = useState(true);

  // The backend keeps the conversation per session id, so follow-up questions work.
  const sessionIdRef = useRef(null);
  const chatBodyRef = useRef(null);

  const sendMessage = async (text) => {
    const question = text.trim();
    if (!question || loading) return;

    setMessages((prev) => [...prev, { role: "user", text: question }]);
    setLoading(true);

    try {
      const response = await fetch(`${API_URL}/chat_query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          input_message: question,
          session_id: sessionIdRef.current,
        }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(
          typeof data.detail === "string" ? data.detail : "Something went wrong. Please try again."
        );
      }
      sessionIdRef.current = data.session_id;
      setMessages((prev) => [...prev, { role: "model", text: data.answer }]);
    } catch (error) {
      const text =
        error instanceof TypeError
          ? "I can't reach the server. Is the backend running on " + API_URL + "?"
          : error.message;
      setMessages((prev) => [...prev, { role: "model", text, isError: true }]);
    } finally {
      setLoading(false);
    }
  };

  const clearChat = () => {
    setMessages([]);
    sessionIdRef.current = null; // start a fresh conversation on the backend too
  };

  // Auto-scroll to the newest message
  useEffect(() => {
    chatBodyRef.current?.scrollTo({ top: chatBodyRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, loading]);

  return (
    <div className={`container ${showChatbot ? "show-chatbot" : ""}`}>
      <main className="landing">
        <h1>Database Chatbot</h1>
        <p>
          Ask questions about a product and supplier database in plain English. An AI agent
          (LangGraph + Gemini) writes the SQL, runs it read-only, and explains the result.
        </p>
      </main>

      <button
        onClick={() => setShowChatbot((prev) => !prev)}
        id="chatbot-toggler"
        aria-label={showChatbot ? "Close chat" : "Open chat"}
      >
        <span className="material-symbols-rounded">mode_comment</span>
        <span className="material-symbols-rounded">close</span>
      </button>

      <div className="chatbot-popup">
        <div className="chat-header">
          <div className="header-info">
            <ChatbotIcon />
            <h2 className="logo-text">Database Chat</h2>
          </div>
          <div className="header-actions">
            <button
              onClick={clearChat}
              className="material-symbols-rounded"
              aria-label="Clear conversation"
              title="Clear conversation"
              disabled={loading || messages.length === 0}
            >
              delete_sweep
            </button>
            <button
              onClick={() => setShowChatbot(false)}
              className="material-symbols-rounded"
              aria-label="Minimize chat"
              title="Minimize"
            >
              keyboard_arrow_down
            </button>
          </div>
        </div>

        <div ref={chatBodyRef} className="chat-body" aria-live="polite">
          <div className="message bot-message">
            <ChatbotIcon />
            <p className="message-text">
              Hey there! <br />
              Ask me anything about the products and suppliers.
            </p>
          </div>

          {messages.length === 0 && (
            <div className="suggestions">
              {SUGGESTIONS.map((s) => (
                <button key={s} className="suggestion-chip" onClick={() => sendMessage(s)}>
                  {s}
                </button>
              ))}
            </div>
          )}

          {messages.map((chat, index) => (
            <ChatMessage key={index} chat={chat} />
          ))}

          {loading && (
            <div className="message bot-message">
              <ChatbotIcon />
              <div className="message-text typing" aria-label="Analyzing the database">
                <span />
                <span />
                <span />
              </div>
            </div>
          )}
        </div>

        <div className="chat-footer">
          <ChatForm onSend={sendMessage} disabled={loading} />
        </div>
      </div>
    </div>
  );
};

export default App;
