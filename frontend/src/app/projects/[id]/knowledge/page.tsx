"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { FormEvent, useCallback, useEffect, useRef, useState } from "react";

import {
  ApiError,
  api,
  type DocumentRecord,
  type ChunkRecord,
  type KnowledgeBase,
  type Project,
} from "@/lib/api";
import { clearSession, useSession } from "@/lib/auth";

type DialogMode = "create-kb" | null;

function ProjectNav({ projectId }: { projectId: number }) {
  return (
    <nav className="mb-6 flex flex-wrap gap-2 border-b border-line pb-3">
      <Link
        href="/dashboard"
        className="rounded-lg px-3 py-1.5 text-sm font-medium text-fg-muted hover:bg-raised"
      >
        Dashboard
      </Link>
      <Link
        href={`/projects/${projectId}`}
        className="rounded-lg px-3 py-1.5 text-sm font-medium text-fg-muted hover:bg-raised"
      >
        Agents
      </Link>
      <Link
        href={`/projects/${projectId}/knowledge`}
        className="rounded-lg bg-accent/10 px-3 py-1.5 text-sm font-semibold text-accent"
      >
        Knowledge Base
      </Link>
      <Link
        href={`/projects/${projectId}/chat`}
        className="rounded-lg px-3 py-1.5 text-sm font-medium text-fg-muted hover:bg-raised"
      >
        Chat
      </Link>
    </nav>
  );
}

function statusBadge(status: string) {
  if (status === "processed") {
    return "bg-emerald-500/10 text-emerald-300";
  }
  if (status === "processing") {
    return "bg-amber-500/10 text-amber-300";
  }
  if (status === "failed") {
    return "bg-red-500/10 text-red-300";
  }
  return "bg-raised text-fg-muted";
}

/** Keep the current document selected if it still exists, else the first. */
function pickSelectedDoc(current: number | null, docs: DocumentRecord[]): number | null {
  if (current && docs.some((doc) => doc.id === current)) {
    return current;
  }
  return docs[0]?.id ?? null;
}

export default function KnowledgePage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const projectId = Number(params.id);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const { ready, token } = useSession();
  const [project, setProject] = useState<Project | null>(null);
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([]);
  const [selectedKbId, setSelectedKbId] = useState<number | null>(null);
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [selectedDocId, setSelectedDocId] = useState<number | null>(null);
  // Chunks are stored with the document they belong to, so switching documents
  // shows nothing (not the previous document's chunks) until the new ones load.
  const [loadedChunks, setLoadedChunks] = useState<{
    docId: number | null;
    chunks: ChunkRecord[];
  }>({ docId: null, chunks: [] });
  const chunks =
    selectedDocId != null && loadedChunks.docId === selectedDocId ? loadedChunks.chunks : [];
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dialog, setDialog] = useState<DialogMode>(null);
  const [kbForm, setKbForm] = useState({ name: "", description: "" });
  const [saving, setSaving] = useState(false);

  const fetchKnowledgeBases = useCallback(
    (authToken: string) =>
      Promise.all([
        api.getProject(authToken, projectId),
        api.listKnowledgeBases(authToken, projectId),
      ]),
    [projectId],
  );

  // Handler versions: effects call the api directly so they can drop late replies.
  async function loadKnowledgeBases(authToken: string) {
    const [projectData, kbList] = await fetchKnowledgeBases(authToken);
    setProject(projectData);
    setKnowledgeBases(kbList);
    if (kbList.length > 0) {
      setSelectedKbId((current) => current ?? kbList[0].id);
    }
  }

  const loadDocuments = useCallback(async (authToken: string, kbId: number) => {
    const docs = await api.listDocuments(authToken, kbId);
    setDocuments(docs);
    setSelectedDocId((current) => pickSelectedDoc(current, docs));
  }, []);

  useEffect(() => {
    if (!Number.isFinite(projectId)) {
      router.replace("/projects");
      return;
    }

    if (!ready) return;
    if (!token) {
      router.replace("/login");
      return;
    }
    let cancelled = false;
    fetchKnowledgeBases(token)
      .then(([projectData, kbList]) => {
        if (cancelled) return;
        setProject(projectData);
        setKnowledgeBases(kbList);
        if (kbList.length > 0) {
          setSelectedKbId((current) => current ?? kbList[0].id);
        }
      })
      .catch((err) => {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 401) {
          clearSession();
          router.replace("/login");
          return;
        }
        router.replace("/projects");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [ready, token, fetchKnowledgeBases, projectId, router]);

  useEffect(() => {
    if (!token || selectedKbId == null) return;
    let cancelled = false;
    api
      .listDocuments(token, selectedKbId)
      .then((docs) => {
        if (cancelled) return;
        setDocuments(docs);
        setSelectedDocId((current) => pickSelectedDoc(current, docs));
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : "Failed to load documents");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [token, selectedKbId]);

  useEffect(() => {
    if (!token || selectedDocId == null) return;
    let cancelled = false;
    api
      .listDocumentChunks(token, selectedDocId)
      .then((chunkList) => {
        if (!cancelled) setLoadedChunks({ docId: selectedDocId, chunks: chunkList });
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : "Failed to load chunks");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [token, selectedDocId]);

  // Ingestion runs as a background task, so the list is polled until nothing is
  // left processing. The dependency is the derived boolean rather than
  // `documents`: polling replaces that array on every tick, which would tear
  // down and rebuild the interval each time instead of running a stable cycle.
  const hasProcessingDocuments = documents.some(
    (doc) => doc.status === "processing",
  );

  useEffect(() => {
    if (!token || selectedKbId == null || !hasProcessingDocuments) return;

    const timer = window.setInterval(() => {
      loadDocuments(token, selectedKbId).catch(() => undefined);
    }, 3000);
    return () => window.clearInterval(timer);
  }, [token, selectedKbId, hasProcessingDocuments, loadDocuments]);

  useEffect(() => {
    if (!token || selectedDocId == null) return;
    const selected = documents.find((doc) => doc.id === selectedDocId);
    if (!selected || selected.status !== "processed") return;
    let cancelled = false;
    api
      .listDocumentChunks(token, selectedDocId)
      .then((chunkList) => {
        if (!cancelled) setLoadedChunks({ docId: selectedDocId, chunks: chunkList });
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [token, selectedDocId, documents]);

  async function onCreateKb(event: FormEvent) {
    event.preventDefault();
    if (!token) return;
    setSaving(true);
    setError(null);
    try {
      const kb = await api.createKnowledgeBase(token, {
        project_id: projectId,
        name: kbForm.name,
        description: kbForm.description || undefined,
      });
      setDialog(null);
      setKbForm({ name: "", description: "" });
      await loadKnowledgeBases(token);
      setSelectedKbId(kb.id);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create knowledge base");
    } finally {
      setSaving(false);
    }
  }

  async function onUpload(file: File) {
    if (!token || selectedKbId == null) return;
    setUploading(true);
    setError(null);
    try {
      await api.uploadDocument(token, selectedKbId, file);
      await loadDocuments(token, selectedKbId);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Upload failed");
    } finally {
      setUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  }

  async function onDeleteDocument(docId: number) {
    if (!token || selectedKbId == null) return;
    setError(null);
    try {
      await api.deleteDocument(token, docId);
      if (selectedDocId === docId) {
        setSelectedDocId(null);
      }
      await loadDocuments(token, selectedKbId);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to delete document");
    }
  }

  if (loading) {
    return (
      <main className="mx-auto flex min-h-dvh max-w-6xl items-center justify-center px-6">
        <p className="text-fg-subtle">Loading knowledge base...</p>
      </main>
    );
  }

  if (!project) return null;

  const selectedKb = knowledgeBases.find((kb) => kb.id === selectedKbId) ?? null;
  const selectedDoc = documents.find((doc) => doc.id === selectedDocId) ?? null;

  return (
    <main className="mx-auto min-h-dvh max-w-6xl px-6 py-10">
      <header className="mb-2">
        <p className="font-display text-sm font-semibold tracking-[0.2em] text-accent uppercase">
          Orchestra
        </p>
        <h1 className="mt-1 font-display text-3xl font-bold">Knowledge Base</h1>
        <p className="mt-1 text-sm text-fg-muted">
          Upload PDF, DOCX, or TXT files. Orchestra extracts text, chunks it, and stores
          embeddings in pgvector.
        </p>
      </header>

      <ProjectNav projectId={projectId} />

      {error && (
        <p className="mb-4 rounded-lg bg-red-500/10 px-3 py-2 text-sm text-red-300">{error}</p>
      )}

      <div className="grid gap-4 lg:grid-cols-[260px_minmax(0,1fr)]">
        <aside className="rounded-2xl border border-line bg-surface/80 p-3">
          <div className="mb-3 flex items-center justify-between gap-2">
            <h2 className="text-sm font-semibold text-fg">Knowledge Bases</h2>
            <button
              onClick={() => setDialog("create-kb")}
              className="rounded-lg bg-accent px-2 py-1 text-xs font-semibold text-ground hover:brightness-110"
            >
              + New
            </button>
          </div>
          <ul className="space-y-1">
            {knowledgeBases.length === 0 && (
              <li className="px-2 py-3 text-xs text-fg-subtle">No knowledge bases yet.</li>
            )}
            {knowledgeBases.map((kb) => (
              <li key={kb.id}>
                <button
                  onClick={() => setSelectedKbId(kb.id)}
                  className={`w-full rounded-lg px-2 py-2 text-left text-sm ${
                    selectedKbId === kb.id
                      ? "bg-accent/10 font-semibold text-accent"
                      : "hover:bg-raised"
                  }`}
                >
                  <span className="block truncate">{kb.name}</span>
                  <span className="mt-0.5 block text-xs text-fg-subtle">
                    {kb.document_count} document{kb.document_count === 1 ? "" : "s"}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </aside>

        <section className="space-y-4">
          {!selectedKb ? (
            <p className="rounded-2xl border border-dashed border-line-strong bg-surface/50 px-4 py-10 text-center text-fg-subtle">
              Create a knowledge base to start uploading documents.
            </p>
          ) : (
            <>
              <div className="rounded-2xl border border-line bg-surface/80 p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <h2 className="font-display text-xl font-semibold">{selectedKb.name}</h2>
                    <p className="mt-1 text-sm text-fg-muted">
                      {selectedKb.description || "No description"}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept=".pdf,.docx,.txt,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain"
                      className="hidden"
                      onChange={(e) => {
                        const file = e.target.files?.[0];
                        if (file) onUpload(file);
                      }}
                    />
                    <button
                      onClick={() => fileInputRef.current?.click()}
                      disabled={uploading}
                      className="rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-ground hover:brightness-110 disabled:opacity-60"
                    >
                      {uploading ? "Uploading..." : "+ Upload Document"}
                    </button>
                  </div>
                </div>
                <p className="mt-2 text-xs text-fg-subtle">
                  Supported: PDF, DOCX, TXT (max 20 MB)
                </p>
              </div>

              <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_320px]">
                <div className="rounded-2xl border border-line bg-surface/80">
                  <div className="border-b border-line px-4 py-3">
                    <h3 className="text-sm font-semibold text-fg">Documents</h3>
                  </div>
                  <ul className="divide-y divide-line">
                    {documents.length === 0 && (
                      <li className="px-4 py-8 text-center text-sm text-fg-subtle">
                        No documents uploaded yet.
                      </li>
                    )}
                    {documents.map((doc) => (
                      <li key={doc.id}>
                        <button
                          onClick={() => setSelectedDocId(doc.id)}
                          className={`flex w-full items-start justify-between gap-3 px-4 py-3 text-left ${
                            selectedDocId === doc.id ? "bg-raised" : "hover:bg-raised/70"
                          }`}
                        >
                          <div className="min-w-0">
                            <p className="truncate text-sm font-medium text-fg">
                              {doc.filename}
                            </p>
                            <p className="mt-1 text-xs text-fg-subtle">
                              Chunks: {doc.chunk_count} · Embedding:{" "}
                              {doc.embedding_status === "generated" ? "Generated" : doc.embedding_status}
                            </p>
                            {doc.error_message && (
                              <p className="mt-1 text-xs text-red-300">{doc.error_message}</p>
                            )}
                          </div>
                          <span
                            className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${statusBadge(doc.status)}`}
                          >
                            {doc.status}
                          </span>
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>

                <aside className="rounded-2xl border border-line bg-surface/80">
                  <div className="border-b border-line px-4 py-3">
                    <h3 className="text-sm font-semibold text-fg">Chunks</h3>
                    {selectedDoc && (
                      <p className="mt-1 truncate text-xs text-fg-subtle">{selectedDoc.filename}</p>
                    )}
                  </div>
                  <div className="max-h-[420px] space-y-2 overflow-y-auto p-3">
                    {!selectedDoc && (
                      <p className="px-1 py-4 text-sm text-fg-subtle">
                        Select a document to inspect chunks.
                      </p>
                    )}
                    {selectedDoc && selectedDoc.status !== "processed" && (
                      <p className="px-1 py-4 text-sm text-fg-subtle">
                        {selectedDoc.status === "processing"
                          ? "Processing document..."
                          : "Document is not ready yet."}
                      </p>
                    )}
                    {selectedDoc?.status === "processed" &&
                      chunks.map((chunk) => (
                        <article
                          key={chunk.id}
                          className="rounded-lg border border-line bg-raised p-3"
                        >
                          <p className="text-xs font-semibold text-fg-subtle">
                            Chunk {chunk.chunk_index + 1}
                          </p>
                          <p className="mt-1 line-clamp-4 text-sm text-fg">
                            {chunk.content}
                          </p>
                        </article>
                      ))}
                  </div>
                  {selectedDoc && (
                    <div className="border-t border-line p-3">
                      <button
                        onClick={() => onDeleteDocument(selectedDoc.id)}
                        className="w-full rounded-lg border border-red-500/30 px-3 py-2 text-sm font-medium text-red-300 hover:bg-red-500/10"
                      >
                        Delete document
                      </button>
                    </div>
                  )}
                </aside>
              </div>
            </>
          )}
        </section>
      </div>

      {dialog === "create-kb" && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-4">
          <form
            onSubmit={onCreateKb}
            className="w-full max-w-lg rounded-2xl border border-line bg-surface p-6 shadow-lg"
          >
            <h2 className="font-display text-xl font-semibold">New Knowledge Base</h2>
            <p className="mt-1 text-sm text-fg-muted">
              Group related documents such as research papers or company docs.
            </p>
            <label className="mt-4 block text-sm">
              <span className="mb-1 block text-fg-muted">Name</span>
              <input
                required
                value={kbForm.name}
                onChange={(e) => setKbForm((f) => ({ ...f, name: e.target.value }))}
                className="w-full rounded-lg border border-line-strong px-3 py-2 outline-none ring-accent focus:ring-2"
                placeholder="Research Papers"
              />
            </label>
            <label className="mt-3 block text-sm">
              <span className="mb-1 block text-fg-muted">Description</span>
              <textarea
                value={kbForm.description}
                onChange={(e) => setKbForm((f) => ({ ...f, description: e.target.value }))}
                className="min-h-24 w-full rounded-lg border border-line-strong px-3 py-2 outline-none ring-accent focus:ring-2"
                placeholder="Optional notes about this collection"
              />
            </label>
            <div className="mt-5 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setDialog(null)}
                className="rounded-lg border border-line-strong px-4 py-2 text-sm font-medium hover:bg-raised"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={saving}
                className="rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-ground hover:brightness-110 disabled:opacity-60"
              >
                {saving ? "Creating..." : "Create"}
              </button>
            </div>
          </form>
        </div>
      )}
    </main>
  );
}
