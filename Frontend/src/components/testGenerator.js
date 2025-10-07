import React, { useState } from "react";

function TestGenerator() {
  const [description, setDescription] = useState("");
  const [collection, setCollection] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const generateCollection = async () => {
    if (!description.trim()) {
      setError("Please enter Jira description.");
      return;
    }

    setLoading(true);
    setError("");

    try {
      const res = await fetch("http://localhost:8000/generate-postman-from-ticket", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ description }),
      });

      if (!res.ok) {
        throw new Error("Failed to generate Postman collection");
      }

      const data = await res.json();
      setCollection(data.postman_collection);
    } catch (err) {
      setError(err.message);
      setCollection(null);
    } finally {
      setLoading(false);
    }
  };

  const copyCollection = () => {
    if (collection) {
      navigator.clipboard.writeText(JSON.stringify(collection, null, 2));
      alert("Postman collection copied to clipboard!");
    }
  };

  const downloadCollection = () => {
    if (collection) {
      const blob = new Blob([JSON.stringify(collection, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "postman_collection.json";
      link.click();
    }
  };

  return (
    <div>
      <textarea
        rows="8"
        style={{ width: "100%", padding: "10px" }}
        placeholder="Paste Jira ticket description here..."
        value={description}
        onChange={(e) => setDescription(e.target.value)}
      />
      <button onClick={generateCollection} disabled={loading} style={{ marginTop: "10px", padding: "10px 20px" }}>
        {loading ? "Generating..." : "Generate Postman Collection"}
      </button>
      {error && <p style={{ color: "red" }}>{error}</p>}
      {collection && (
        <div style={{ marginTop: "20px" }}>
          <button onClick={copyCollection} style={{ marginRight: "10px", padding: "10px 20px" }}>Copy Collection</button>
          <button onClick={downloadCollection} style={{ padding: "10px 20px" }}>Download Collection</button>
        </div>
      )}
    </div>
  );
}

export default TestGenerator;
