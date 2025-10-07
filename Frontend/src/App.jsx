import React, { useState } from "react";
import "./App.css";

function App() {
  const [summary, setSummary] = useState("");
  const [description, setDescription] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [collection, setCollection] = useState(null);

  const handleGenerate = async () => {
    if (!description.trim()) {
      setError("Ticket description is required");
      return;
    }

    setLoading(true);
    setError("");
    setCollection(null);

    try {
      const response = await fetch(
        "http://localhost:8000/generate",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            summary: summary || "Untitled",
            description,
          }),
        }
      );

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || "Failed to generate test cases");
      }

      const data = await response.json();
      setCollection(data.postman_collection);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleDownload = () => {
    if (!collection) return;
    const blob = new Blob([JSON.stringify(collection, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "postman_collection.json";
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="app-container">
      <h1>AI-Powered Postman Collection Generator</h1>

      <div className="form-group">
        <label>Ticket Summary (optional)</label>
        <input
          type="text"
          value={summary}
          onChange={(e) => setSummary(e.target.value)}
          placeholder="Enter ticket summary"
        />
      </div>

      <div className="form-group">
        <label>Ticket Description *</label>
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Enter ticket description"
          rows={6}
        />
      </div>

      <button onClick={handleGenerate} disabled={loading}>
        {loading ? "Generating..." : "Generate Collection"}
      </button>

      {error && <div className="error">{error}</div>}

      {collection && (
        <div className="collection-container">
          <h2>Generated Postman Collection</h2>
          <pre>{JSON.stringify(collection, null, 2)}</pre>
          <button onClick={handleDownload}>Download JSON</button>
        </div>
      )}
    </div>
  );
}

export default App;
