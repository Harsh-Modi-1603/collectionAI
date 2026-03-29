import React, { useState, useRef, useEffect } from "react";
import "./App.css";
import { parseTicketIds, deriveFilename } from "./utils";

const API_BASE = process.env.REACT_APP_API_BASE || "http://localhost:8000";

function App() {
  const [mode, setMode] = useState("tickets");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [collection, setCollection] = useState(null);
  const [warnings, setWarnings] = useState([]);

  // Manual mode
  const [summary, setSummary] = useState("");
  const [description, setDescription] = useState("");

  // Ticket IDs mode
  const [ticketInput, setTicketInput] = useState("");
  const [collectionName, setCollectionName] = useState("");

  // Chat mode
  const [chatMessages, setChatMessages] = useState([]);
  const [chatInput, setChatInput] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const [showChat, setShowChat] = useState(false);
  const chatEndRef = useRef(null);

  // Auto-scroll chat to bottom
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatMessages]);

  const handleGenerateManual = async () => {
    if (!description.trim()) {
      setError("Ticket description is required");
      return;
    }
    setLoading(true);
    setError("");
    setCollection(null);
    setWarnings([]);
    setChatMessages([]);
    try {
      const response = await fetch(`${API_BASE}/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ summary: summary || "Untitled", description }),
      });
      if (!response.ok) {
        const d = await response.json();
        throw new Error(d.detail || "Failed");
      }
      const data = await response.json();
      setCollection(data.postman_collection);
      setShowChat(true);
    } catch (err) {
      setError(
        err.message.length > 200
          ? "Something went wrong. Please try again."
          : err.message
      );
    } finally {
      setLoading(false);
    }
  };

  const handleGenerateFromTickets = async () => {
    const ids = parseTicketIds(ticketInput);
    if (ids.length === 0) {
      setError("Enter at least one JIRA ticket ID");
      return;
    }
    setLoading(true);
    setError("");
    setCollection(null);
    setWarnings([]);
    setChatMessages([]);
    try {
      const response = await fetch(`${API_BASE}/generate-from-tickets`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ticket_ids: ids,
          collection_name: collectionName.trim() || undefined,
        }),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || "Failed to generate collection");
      }
      setCollection(data.postman_collection);
      setWarnings(data.warnings || []);
      setShowChat(true);
    } catch (err) {
      setError(
        err.message.length > 200
          ? "Something went wrong. Please try again."
          : err.message
      );
    } finally {
      setLoading(false);
    }
  };

  const handleDownload = () => {
    if (!collection) return;
    const ids = mode === "tickets" ? parseTicketIds(ticketInput) : [];
    const filename =
      mode === "tickets"
        ? deriveFilename(collectionName.trim(), ids)
        : "postman_collection.json";
    const blob = new Blob([JSON.stringify(collection, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleCopy = () => {
    if (!collection) return;
    navigator.clipboard.writeText(JSON.stringify(collection, null, 2));
    // Show toast notification
    const toast = document.createElement("div");
    toast.className = "toast";
    toast.textContent = "✓ Copied to clipboard!";
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 2000);
  };

  const handleChatSend = async () => {
    if (!chatInput.trim()) return;

    const userMessage = chatInput.trim();
    setChatInput("");

    // Add user message to chat
    const newMessages = [
      ...chatMessages,
      { role: "user", content: userMessage },
    ];
    setChatMessages(newMessages);
    setChatLoading(true);

    try {
      // Check if user wants to modify collection or just chat
      const modifyKeywords = [
        "add",
        "remove",
        "delete",
        "change",
        "modify",
        "update",
        "create",
      ];
      const isModifyRequest = modifyKeywords.some((keyword) =>
        userMessage.toLowerCase().includes(keyword)
      );

      if (isModifyRequest && collection) {
        // Modify collection
        const response = await fetch(`${API_BASE}/refine-collection`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            existing_collection: collection,
            user_message: userMessage,
          }),
        });

        const data = await response.json();
        if (!response.ok) {
          // Show user-friendly error message
          const errorMessage = data.detail || "Unable to modify collection. Please try again.";
          setChatMessages([
            ...newMessages,
            {
              role: "assistant",
              content: `I'm having trouble modifying the collection right now. ${errorMessage}`,
            },
          ]);
          return;
        }

        setCollection(data.refined_collection);
        setChatMessages([
          ...newMessages,
          {
            role: "assistant",
            content: `✓ ${data.message || "Collection updated successfully!"}`,
          },
        ]);
      } else {
        // Just chat
        const response = await fetch(`${API_BASE}/chat`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            message: userMessage,
            collection: collection,
            history: chatMessages.slice(-10),
          }),
        });

        const data = await response.json();
        
        // Chat endpoint returns success/failure in response body, not HTTP status
        if (data.success) {
          setChatMessages([
            ...newMessages,
            { role: "assistant", content: data.response },
          ]);
        } else {
          // Show the friendly error message from backend
          setChatMessages([
            ...newMessages,
            { role: "assistant", content: data.response },
          ]);
        }
      }
    } catch (err) {
      // Generic fallback for unexpected errors
      setChatMessages([
        ...newMessages,
        {
          role: "assistant",
          content: "I'm having trouble right now. Please try again in a moment.",
        },
      ]);
    } finally {
      setChatLoading(false);
    }
  };

  return (
    <div className="app-container">
      <header className="app-header">
        <div className="header-content">
          <div className="logo">
            <span className="logo-icon">🚀</span>
            <h1>CollectionAI</h1>
          </div>
          <p className="tagline">
            AI-Powered Postman Collection Generator
          </p>
        </div>
      </header>

      <main className="main-content">
        <div className="input-section">
          <div className="mode-toggle">
            <button
              className={mode === "tickets" ? "tab active" : "tab"}
              onClick={() => {
                setMode("tickets");
                setError("");
                setCollection(null);
                setWarnings([]);
                setChatMessages([]);
              }}
            >
              <span className="tab-icon">🎫</span>
              JIRA Tickets
            </button>
            <button
              className={mode === "manual" ? "tab active" : "tab"}
              onClick={() => {
                setMode("manual");
                setError("");
                setCollection(null);
                setWarnings([]);
                setChatMessages([]);
              }}
            >
              <span className="tab-icon">✍️</span>
              Manual Input
            </button>
          </div>

          <div className="input-form">
            {mode === "manual" && (
              <>
                <div className="form-group">
                  <label>
                    <span className="label-icon">📝</span>
                    Ticket Summary (optional)
                  </label>
                  <input
                    type="text"
                    value={summary}
                    onChange={(e) => setSummary(e.target.value)}
                    placeholder="e.g., User Authentication Feature"
                    disabled={loading}
                  />
                </div>
                <div className="form-group">
                  <label>
                    <span className="label-icon">📄</span>
                    Ticket Description *
                  </label>
                  <textarea
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    placeholder="Describe the feature or API you want to test..."
                    rows={6}
                    disabled={loading}
                  />
                </div>
                <button
                  className="generate-btn"
                  onClick={handleGenerateManual}
                  disabled={loading}
                >
                  {loading ? (
                    <>
                      <span className="spinner"></span>
                      Generating...
                    </>
                  ) : (
                    <>
                      <span className="btn-icon">✨</span>
                      Generate Collection
                    </>
                  )}
                </button>
              </>
            )}

            {mode === "tickets" && (
              <>
                <div className="form-group">
                  <label>
                    <span className="label-icon">🎫</span>
                    JIRA Ticket IDs *
                  </label>
                  <textarea
                    value={ticketInput}
                    onChange={(e) => setTicketInput(e.target.value)}
                    placeholder={"CB-4350\nCB-1234, CB-5678"}
                    rows={4}
                    disabled={loading}
                  />
                  <span className="input-hint">
                    Enter ticket IDs separated by commas or newlines
                  </span>
                </div>
                <div className="form-group">
                  <label>
                    <span className="label-icon">📦</span>
                    Collection Name (optional)
                  </label>
                  <input
                    type="text"
                    value={collectionName}
                    onChange={(e) => setCollectionName(e.target.value)}
                    placeholder="e.g., Campaign Feature E2E Tests"
                    disabled={loading}
                  />
                </div>
                <button
                  className="generate-btn"
                  onClick={handleGenerateFromTickets}
                  disabled={loading}
                >
                  {loading ? (
                    <>
                      <span className="spinner"></span>
                      Generating...
                    </>
                  ) : (
                    <>
                      <span className="btn-icon">✨</span>
                      Generate Collection
                    </>
                  )}
                </button>
              </>
            )}
          </div>

          {error && (
            <div className="error-banner">
              <span className="error-icon">⚠️</span>
              {error}
            </div>
          )}

          {warnings && warnings.length > 0 && (
            <div className="warnings-banner">
              <span className="warning-icon">⚠️</span>
              <div className="warning-content">
                <strong>Warnings:</strong>
                <ul>
                  {warnings.map((warning, index) => (
                    <li key={index}>{warning}</li>
                  ))}
                </ul>
              </div>
            </div>
          )}
        </div>

        {collection && (
          <div className="results-section">
            <div className="results-header">
              <h2>
                <span className="section-icon">✅</span>
                Generated Collection
              </h2>
              <div className="action-buttons">
                <button className="action-btn download" onClick={handleDownload}>
                  <span className="btn-icon">⬇️</span>
                  Download
                </button>
                <button className="action-btn copy" onClick={handleCopy}>
                  <span className="btn-icon">📋</span>
                  Copy
                </button>
                <button
                  className="action-btn chat-toggle"
                  onClick={() => setShowChat(!showChat)}
                >
                  <span className="btn-icon">💬</span>
                  {showChat ? "Hide" : "Show"} Chat
                </button>
              </div>
            </div>

            <div className="results-content">
              {showChat && (
                <div className="chat-panel">
                  <div className="chat-header">
                    <span className="chat-icon">🤖</span>
                    <h3>AI Assistant</h3>
                  </div>

                  <div className="chat-messages">
                    {chatMessages.length === 0 && (
                      <div className="chat-welcome">
                        <p>👋 Hi! I'm your AI assistant.</p>
                        <p>Ask me anything about your collection or request changes!</p>
                        <div className="chat-suggestions">
                          <button
                            onClick={() =>
                              setChatInput("Explain what this collection does")
                            }
                          >
                            Explain this collection
                          </button>
                          <button
                            onClick={() =>
                              setChatInput("Add a DELETE request for campaigns")
                            }
                          >
                            Add DELETE request
                          </button>
                          <button
                            onClick={() =>
                              setChatInput("How do I run this in Postman?")
                            }
                          >
                            How to use in Postman?
                          </button>
                        </div>
                      </div>
                    )}

                    {chatMessages.map((msg, idx) => (
                      <div key={idx} className={`chat-message ${msg.role}`}>
                        <div className="message-avatar">
                          {msg.role === "user" ? "👤" : "🤖"}
                        </div>
                        <div className="message-content">
                          <div className="message-text">{msg.content}</div>
                        </div>
                      </div>
                    ))}

                    {chatLoading && (
                      <div className="chat-message assistant">
                        <div className="message-avatar">🤖</div>
                        <div className="message-content">
                          <div className="typing-indicator">
                            <span></span>
                            <span></span>
                            <span></span>
                          </div>
                        </div>
                      </div>
                    )}

                    <div ref={chatEndRef} />
                  </div>

                  <div className="chat-input-container">
                    <input
                      type="text"
                      value={chatInput}
                      onChange={(e) => setChatInput(e.target.value)}
                      onKeyPress={(e) =>
                        e.key === "Enter" && !chatLoading && handleChatSend()
                      }
                      placeholder="Ask a question or request changes..."
                      disabled={chatLoading}
                    />
                    <button
                      onClick={handleChatSend}
                      disabled={chatLoading || !chatInput.trim()}
                      className="send-btn"
                    >
                      <span className="btn-icon">📤</span>
                    </button>
                  </div>
                </div>
              )}

              <div className="collection-preview">
                <div className="preview-header">
                  <span className="preview-icon">📄</span>
                  <h3>Collection JSON</h3>
                  <span className="preview-count">
                    {collection.item?.length || 0} requests
                  </span>
                </div>
                <pre className="json-preview">
                  {JSON.stringify(collection, null, 2)}
                </pre>
              </div>
            </div>
          </div>
        )}
      </main>

      <footer className="app-footer">
        <p>Made with ❤️ for IQM QA Team</p>
      </footer>
    </div>
  );
}

export default App;
