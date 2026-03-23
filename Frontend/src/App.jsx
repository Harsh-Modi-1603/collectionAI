import React, { useState } from "react";
import "./App.css";
import { parseTicketIds, deriveFilename } from "./utils";

const API_BASE = process.env.REACT_APP_API_BASE || "http://localhost:8000";

function App() {
  const [mode, setMode] = useState("manual");
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

  const handleGenerateManual = async () => {
    if (!description.trim()) { setError("Ticket description is required"); return; }
    setLoading(true); setError(""); setCollection(null); setWarnings([]);
    try {
      const response = await fetch(`${API_BASE}/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ summary: summary || "Untitled", description }),
      });
      if (!response.ok) { const d = await response.json(); throw new Error(d.detail || "Failed"); }
      const data = await response.json();
      setCollection(data.postman_collection);
    } catch (err) { setError(err.message.length > 200 ? "Something went wrong. Please try again." : err.message); }
    finally { setLoading(false); }
  };

  const handleGenerateFromTickets = async () => {
    const ids = parseTicketIds(ticketInput);
    if (ids.length === 0) { setError("Enter at least one JIRA ticket ID"); return; }
    setLoading(true); setError(""); setCollection(null); setWarnings([]);
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
    } catch (err) { setError(err.message.length > 200 ? "Something went wrong. Please try again." : err.message); }
    finally { setLoading(false); }
  };

  const handleDownload = () => {
    if (!collection) return;
    const ids = mode === "tickets" ? parseTicketIds(ticketInput) : [];
    const filename = mode === "tickets" ? deriveFilename(collectionName.trim(), ids) : "postman_collection.json";
    const blob = new Blob([JSON.stringify(collection, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = filename; a.click();
    URL.revokeObjectURL(url);
  };

  const handleCopy = () => {
    if (!collection) return;
    navigator.clipboard.writeText(JSON.stringify(collection, null, 2));
  };

  return (
    <div className="app-container">
      <h1>AI-Powered Postman Collection Generator</h1>

      <div className="mode-toggle">
        <button className={mode === "manual" ? "tab active" : "tab"}
          onClick={() => { setMode("manual"); setError(""); setCollection(null); setWarnings([]); }}>
          Manual
        </button>
        <button className={mode === "tickets" ? "tab active" : "tab"}
          onClick={() => { setMode("tickets"); setError(""); setCollection(null); setWarnings([]); }}>
          Ticket IDs
        </button>
      </div>

      {mode === "manual" && (
        <>
          <div className="form-group">
            <label>Ticket Summary (optional)</label>
            <input type="text" value={summary} onChange={(e) => setSummary(e.target.value)} placeholder="Enter ticket summary" />
          </div>
          <div className="form-group">
            <label>Ticket Description *</label>
            <textarea value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Enter ticket description" rows={6} />
          </div>
          <button onClick={handleGenerateManual} disabled={loading}>
            {loading ? "Generating... (this may take up to 30s)" : "Generate Collection"}
          </button>
        </>
      )}

      {mode === "tickets" && (
        <>
          <div className="form-group">
            <label>JIRA Ticket IDs *</label>
            <textarea value={ticketInput} onChange={(e) => setTicketInput(e.target.value)}
              placeholder={"Enter ticket IDs, comma or newline separated\ne.g. PROJ-123, PROJ-124\nPROJ-125"} rows={5} />
          </div>
          <div className="form-group">
            <label>Collection Name (optional)</label>
            <input type="text" value={collectionName} onChange={(e) => setCollectionName(e.target.value)}
              placeholder="e.g. Campaign Feature E2E" />
          </div>
          <button onClick={handleGenerateFromTickets} disabled={loading}>
            {loading ? "Generating... (this may take up to 30s)" : "Generate Collection"}
          </button>
        </>
      )}

      {error && <div className="error">{error}</div>}

      {collection && (
        <div className="collection-container">
          <h2>Generated Postman Collection</h2>
          <div className="collection-actions">
            <button onClick={handleDownload}>Download JSON</button>
            <button onClick={handleCopy}>Copy to Clipboard</button>
          </div>
          <pre>{JSON.stringify(collection, null, 2)}</pre>
        </div>
      )}
    </div>
  );
}

export default App;
