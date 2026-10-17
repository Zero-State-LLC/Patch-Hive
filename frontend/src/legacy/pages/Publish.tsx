import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { publishingApi } from "@/legacy/apiClients";
import { rackApi, patchApi } from "@/lib/api";
import { useAuthStore } from "@/lib/store";
import type { ExportRecord, Rack, Patch } from "@/types/api";

export default function PublishPage() {
  const { user, isAuthenticated } = useAuthStore();
  const [exports, setExports] = useState<ExportRecord[]>([]);
  const [racks, setRacks] = useState<Rack[]>([]);
  const [patches, setPatches] = useState<Patch[]>([]);
  const [sourceType, setSourceType] = useState<"rack" | "patch">("rack");
  const [selectedRackId, setSelectedRackId] = useState<number | "">("");
  const [selectedPatchId, setSelectedPatchId] = useState<number | "">("");
  const [selectedExportId, setSelectedExportId] = useState<number | "">("");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [visibility, setVisibility] = useState<"public" | "unlisted">("unlisted");
  const [allowDownload, setAllowDownload] = useState(true);
  const [allowRemix, setAllowRemix] = useState(false);
  const [coverImageUrl, setCoverImageUrl] = useState("");
  const [status, setStatus] = useState<string | null>(null);

  const exportOptions = useMemo(() => exports.filter(Boolean), [exports]);

  const fetchExports = async () => {
    const response = await publishingApi.listExports();
    setExports(response.data);
  };

  const fetchRacks = async () => {
    if (!user) return;
    const response = await rackApi.list({ user_id: user.id });
    setRacks(response.data.racks);
  };

  const fetchPatches = async (rackId: number) => {
    const response = await patchApi.list({ rack_id: rackId });
    setPatches(response.data.patches);
  };

  useEffect(() => {
    if (isAuthenticated()) {
      fetchExports();
      fetchRacks();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAuthenticated]);

  useEffect(() => {
    if (sourceType === "patch" && selectedRackId) {
      fetchPatches(Number(selectedRackId));
    }
  }, [sourceType, selectedRackId]);

  const handleCreateExport = async () => {
    setStatus(null);
    try {
      const sourceId = sourceType === "rack" ? selectedRackId : selectedPatchId;
      if (!sourceId) {
        setStatus("Select an export source.");
        return;
      }
      await publishingApi.createExport({ source_type: sourceType, source_id: Number(sourceId) });
      await fetchExports();
      setStatus("Export generated.");
    } catch {
      setStatus("Unable to generate export.");
    }
  };

  const handlePublish = async () => {
    setStatus(null);
    if (!selectedExportId) {
      setStatus("Select an export to publish.");
      return;
    }
    try {
      await publishingApi.createPublication({
        export_id: Number(selectedExportId),
        title,
        description: description || undefined,
        visibility,
        allow_download: allowDownload,
        allow_remix: allowRemix,
        cover_image_url: coverImageUrl || undefined,
      });
      setTitle("");
      setDescription("");
      setCoverImageUrl("");
      setStatus("Publication created.");
    } catch {
      setStatus("Unable to publish export.");
    }
  };

  if (!isAuthenticated()) {
    return <p>Please log in to publish exports.</p>;
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "2rem" }}>
      <Link to="/account" style={{ color: "#00ff88" }}>
        ← Back to account
      </Link>

      <section
        style={{
          background: "#111",
          border: "1px solid #222",
          borderRadius: "8px",
          padding: "1.5rem",
        }}
      >
        <h2 style={{ marginTop: 0 }}>Publish</h2>
        <p style={{ color: "#aaa" }}>Generate export artifacts and publish when ready.</p>
        <div
          style={{
            display: "grid",
            gap: "1rem",
            gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
          }}
        >
          <div>
            <label style={{ display: "block", color: "#ccc" }}>
              Export source
              <select
                value={sourceType}
                onChange={(event) => setSourceType(event.target.value as "rack" | "patch")}
                style={{
                  width: "100%",
                  marginTop: "0.4rem",
                  background: "#0d0d0d",
                  color: "#fff",
                  border: "1px solid #333",
                  borderRadius: "4px",
                  padding: "0.4rem",
                }}
              >
                <option value="rack">Rack export</option>
                <option value="patch">Patch export</option>
              </select>
            </label>
          </div>
          <div>
            <label style={{ display: "block", color: "#ccc" }}>
              Rack
              <select
                value={selectedRackId}
                onChange={(event) =>
                  setSelectedRackId(event.target.value ? Number(event.target.value) : "")
                }
                style={{
                  width: "100%",
                  marginTop: "0.4rem",
                  background: "#0d0d0d",
                  color: "#fff",
                  border: "1px solid #333",
                  borderRadius: "4px",
                  padding: "0.4rem",
                }}
              >
                <option value="">Select a rack</option>
                {racks.map((rack) => (
                  <option key={rack.id} value={rack.id}>
                    {rack.name}
                  </option>
                ))}
              </select>
            </label>
          </div>
          {sourceType === "patch" && (
            <div>
              <label style={{ display: "block", color: "#ccc" }}>
                Patch
                <select
                  value={selectedPatchId}
                  onChange={(event) =>
                    setSelectedPatchId(event.target.value ? Number(event.target.value) : "")
                  }
                  style={{
                    width: "100%",
                    marginTop: "0.4rem",
                    background: "#0d0d0d",
                    color: "#fff",
                    border: "1px solid #333",
                    borderRadius: "4px",
                    padding: "0.4rem",
                  }}
                >
                  <option value="">Select a patch</option>
                  {patches.map((patch) => (
                    <option key={patch.id} value={patch.id}>
                      {patch.name}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          )}
        </div>
        <button
          onClick={handleCreateExport}
          style={{
            marginTop: "1rem",
            background: "#222",
            color: "#fff",
            border: "1px solid #333",
            padding: "0.5rem 1rem",
            borderRadius: "6px",
            cursor: "pointer",
          }}
        >
          Generate export
        </button>
      </section>

      <section
        style={{
          background: "#111",
          border: "1px solid #222",
          borderRadius: "8px",
          padding: "1.5rem",
        }}
      >
        <h3 style={{ marginTop: 0 }}>Publication details</h3>
        <div style={{ display: "grid", gap: "1rem" }}>
          <label style={{ color: "#ccc" }}>
            Export
            <select
              value={selectedExportId}
              onChange={(event) =>
                setSelectedExportId(event.target.value ? Number(event.target.value) : "")
              }
              style={{
                width: "100%",
                marginTop: "0.4rem",
                background: "#0d0d0d",
                color: "#fff",
                border: "1px solid #333",
                borderRadius: "4px",
                padding: "0.4rem",
              }}
            >
              <option value="">Select an export</option>
              {exportOptions.map((exportRecord) => (
                <option key={exportRecord.id} value={exportRecord.id}>
                  {exportRecord.export_type.toUpperCase()} export #{exportRecord.id}
                </option>
              ))}
            </select>
          </label>
          <label style={{ color: "#ccc" }}>
            Title
            <input
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              style={{
                width: "100%",
                marginTop: "0.4rem",
                background: "#0d0d0d",
                color: "#fff",
                border: "1px solid #333",
                borderRadius: "4px",
                padding: "0.4rem",
              }}
            />
          </label>
          <label style={{ color: "#ccc" }}>
            Description
            <textarea
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              rows={3}
              style={{
                width: "100%",
                marginTop: "0.4rem",
                background: "#0d0d0d",
                color: "#ccc",
                border: "1px solid #333",
                borderRadius: "4px",
                padding: "0.4rem",
              }}
            />
          </label>
          <label style={{ color: "#ccc" }}>
            Cover image URL
            <input
              value={coverImageUrl}
              onChange={(event) => setCoverImageUrl(event.target.value)}
              style={{
                width: "100%",
                marginTop: "0.4rem",
                background: "#0d0d0d",
                color: "#fff",
                border: "1px solid #333",
                borderRadius: "4px",
                padding: "0.4rem",
              }}
            />
          </label>
          <label style={{ color: "#ccc" }}>
            Visibility
            <select
              value={visibility}
              onChange={(event) => setVisibility(event.target.value as "public" | "unlisted")}
              style={{
                width: "100%",
                marginTop: "0.4rem",
                background: "#0d0d0d",
                color: "#fff",
                border: "1px solid #333",
                borderRadius: "4px",
                padding: "0.4rem",
              }}
            >
              <option value="unlisted">Unlisted</option>
              <option value="public">Public</option>
            </select>
          </label>
          <label style={{ color: "#ccc" }}>
            Allow download
            <input
              type="checkbox"
              checked={allowDownload}
              onChange={(event) => setAllowDownload(event.target.checked)}
              style={{ marginLeft: "0.5rem" }}
            />
          </label>
          <label style={{ color: "#ccc" }}>
            Allow remix
            <input
              type="checkbox"
              checked={allowRemix}
              onChange={(event) => setAllowRemix(event.target.checked)}
              style={{ marginLeft: "0.5rem" }}
            />
          </label>
        </div>
        <button
          onClick={handlePublish}
          style={{
            marginTop: "1rem",
            background: "#00ff88",
            color: "#000",
            border: "none",
            padding: "0.6rem 1.2rem",
            borderRadius: "6px",
            cursor: "pointer",
            fontWeight: "bold",
          }}
        >
          Publish
        </button>
        {status && <p style={{ color: "#aaa", marginTop: "0.6rem" }}>{status}</p>}
      </section>
    </div>
  );
}
