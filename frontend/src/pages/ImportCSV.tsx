import { useState, useRef, type DragEvent } from "react";
import { api } from "../api/client";

export default function ImportCSV() {
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFile = (f: File) => {
    if (f.name.endsWith(".csv")) {
      setFile(f);
      setMessage(null);
    } else {
      setMessage({ type: "error", text: "Only CSV files are accepted." });
    }
  };

  const handleDrop = (e: DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    if (e.dataTransfer.files[0]) handleFile(e.dataTransfer.files[0]);
  };

  const handleUpload = async () => {
    if (!file) return;
    setUploading(true);
    setMessage(null);
    try {
      const result = await api.uploadCSV(file);
      setMessage({ type: "success", text: result.message });
      setFile(null);
    } catch (err) {
      setMessage({ type: "error", text: err instanceof Error ? err.message : "Upload failed" });
    } finally {
      setUploading(false);
    }
  };

  return (
    <div>
      <div className="card">
        <h2>Import IBKR CSV Statement</h2>
        <p style={{ color: "#64748b", marginBottom: 20 }}>
          Upload your Interactive Brokers Activity Statement CSV file to import trade data.
        </p>

        {message && <div className={`alert alert-${message.type}`}>{message.text}</div>}

        <div
          className={`drop-zone ${dragOver ? "drop-zone-active" : ""}`}
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          onClick={() => inputRef.current?.click()}
        >
          <input
            ref={inputRef}
            type="file"
            accept=".csv"
            style={{ display: "none" }}
            onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
          />
          {file ? (
            <div>
              <div style={{ fontSize: 18, fontWeight: 600 }}>{file.name}</div>
              <div style={{ color: "#64748b", marginTop: 4 }}>
                {(file.size / 1024).toFixed(1)} KB
              </div>
            </div>
          ) : (
            <div>
              <div style={{ fontSize: 32, marginBottom: 8 }}>CSV</div>
              <div>Drag & drop CSV file here or click to browse</div>
            </div>
          )}
        </div>

        <button
          className="btn btn-primary"
          onClick={handleUpload}
          disabled={!file || uploading}
          style={{ marginTop: 16 }}
        >
          {uploading ? "Uploading..." : "Upload & Import"}
        </button>
      </div>
    </div>
  );
}
