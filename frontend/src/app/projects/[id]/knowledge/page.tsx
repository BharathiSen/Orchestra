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
import { clearSession, getToken } from "@/lib/auth";

type DialogMode = "create-kb" | null;

function ProjectNav({ projectId }: { projectId: number }) {
  return (
    <nav className="mb-6 flex flex-wrap gap-2 border-b border-slate-200 pb-3">
      <Link
        href="/dashboard"
        className="rounded-lg px-3 py-1.5 text-sm font-medium text-slate-600 hover:bg-slate-100"
      >
        Dashboard
      </Link>
      <Link
        href={`/projects/${projectId}`}
        className="rounded-lg px-3 py-1.5 text-sm font-medium text-slate-600 hover:bg-slate-100"
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
        className="rounded-lg px-3 py-1.5 text-sm font-medium text-slate-600 hover:bg-slate-100"
      >
        Chat
      </Link>
    </nav>
  );
}

function statusBadge(status: string) {
  if (status === "processed") {
    return "bg-emerald-50 text-emerald-700";
  }
  if (status === "processing") {
    return "bg-amber-50 text-amber-700";
  }
  if (status === "failed") {
    return "bg-red-50 text-red-700";
  }
  return "bg-slate-100 text-slate-600";
}

export default function KnowledgePage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const projectId = Number(params.id);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [token, setToken] = useState<string | null>(null);
  const [project, setProject] = useState<Project | null>(null);
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([]);
  const [selectedKbId, setSelectedKbId] = useState<number | null>(null);
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [selectedDocId, setSelectedDocId] = useState<number | null>(null);
  const [chunks, setChunks] = useState<ChunkRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dialog, setDialog] = useState<DialogMode>(null);
  const [kbForm, setKbForm] = useState({ name: "", description: "" });
  const [saving, setSaving] = useState(false);

  const loadKnowledgeBases = useCallback(
    async (authToken: string) => {
      const [projectData, kbList] = await Promise.all([
        api.getProject(authToken, projectId),
        api.listKnowledgeBases(authToken, projectId),
      ]);
      setProject(projectData);
      setKnowledgeBases(kbList);
      if (kbList.length > 0) {
        setSelectedKbId((current) => current ?? kbList[0].id);
      }
    },
    [projectId],
  );

  const loadDocuments = useCallback(async (authToken: string, kbId: number) => {
    const docs = await api.listDocuments(authToken, kbId);
    setDocuments(docs);
    setSelectedDocId((current) => {
      if (current && docs.some((doc) => doc.id === current)) {
        return current;
      }
      return docs[0]?.id ?? null;
    });
  }, []);

  const loadChunks = useCallback(async (authToken: string, docId: number) => {
    const chunkList = await api.listDocumentChunks(authToken, docId);
    setChunks(chunkList);
  }, []);

  useEffect(() => {
    if (!Number.isFinite(projectId)) {
      router.replace("/projects");
      return;
    }

    const authToken = getToken();
    if (!authToken) {
      router.replace("/login");
      return;
    }
    setToken(authToken);
    loadKnowledgeBases(authToken)
      .catch((err) => {
        if (err instanceof ApiError && err.status === 401) {
          clearSession();
          router.replace("/login");
          return;
        }
        router.replace("/projects");
      })
      .finally(() => setLoading(false));
  }, [loadKnowledgeBases, projectId, router]);

  useEffect(() => {
    if (!token || selectedKbId == null) return;
    loadDocuments(token, selectedKbId).catch((err) => {
      setError(err instanceof ApiError ? err.message : "Failed to load documents");
    });
  }, [token, selectedKbId, loadDocuments]);

  useEffect(() => {
    if (!token || selectedDocId == null) {
      setChunks([]);
      return;
    }
    loadChunks(token, selectedDocId).catch((err) => {
      setError(err instanceof ApiError ? err.message : "Failed to load chunks");
    });
  }, [token, selectedDocId, loadChunks]);

  useEffect(() => {
    if (!token || selectedKbId == null) return;
    const hasProcessing = documents.some((doc) => doc.status === "processing");
    if (!hasProcessing) return;

    const timer = window.setInterval(() => {
      loadDocuments(token, selectedKbId).catch(() => undefined);
    }, 3000);
    return () => window.clearInterval(timer);
  }, [token, selectedKbId, documents, loadDocuments]);

  useEffect(() => {
    if (!token || selectedDocId == null) return;
    const selected = documents.find((doc) => doc.id === selectedDocId);
    if (!selected || selected.status !== "processed") return;
    loadChunks(token, selectedDocId).catch(() => undefined);
  }, [token, selectedDocId, documents, loadChunks]);

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
        setChunks([]);
      }
      await loadDocuments(token, selectedKbId);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to delete document");
    }
  }

  if (loading) {
    return (
      <main className="mx-auto flex min-h-screen max-w-6xl items-center justify-center px-6">
        <p className="text-slate-500">Loading knowledge base...</p>
      </main>
    );
  }

  if (!project) return null;

  const selectedKb = knowledgeBases.find((kb) => kb.id === selectedKbId) ?? null;
  const selectedDoc = documents.find((doc) => doc.id === selectedDocId) ?? null;

  return (
    <main className="mx-auto min-h-screen max-w-6xl px-6 py-10">
      <header className="mb-2">
        <p className="font-display text-sm font-semibold tracking-[0.2em] text-accent uppercase">
          Orchestra
        </p>
        <h1 className="mt-1 font-display text-3xl font-bold">Knowledge Base</h1>
        <p className="mt-1 text-sm text-slate-600">
          Upload PDF, DOCX, or TXT files. Orchestra extracts text, chunks it, and stores
          embeddings in pgvector.
        </p>
      </header>

      <ProjectNav projectId={projectId} />

      {error && (
        <p className="mb-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>
      )}

      <div className="grid gap-4 lg:grid-cols-[260px_minmax(0,1fr)]">
        <aside className="rounded-2xl border border-slate-200 bg-white/80 p-3">
          <div className="mb-3 flex items-center justify-between gap-2">
            <h2 className="text-sm font-semibold text-slate-700">Knowledge Bases</h2>
            <button
              onClick={() => setDialog("create-kb")}
              className="rounded-lg bg-accent px-2 py-1 text-xs font-semibold text-white hover:bg-teal-700"
            >
              + New
            </button>
          </div>
          <ul className="space-y-1">
            {knowledgeBases.length === 0 && (
              <li className="px-2 py-3 text-xs text-slate-500">No knowledge bases yet.</li>
            )}
            {knowledgeBases.map((kb) => (
              <li key={kb.id}>
                <button
                  onClick={() => setSelectedKbId(kb.id)}
                  className={`w-full rounded-lg px-2 py-2 text-left text-sm ${
                    selectedKbId === kb.id
                      ? "bg-accent/10 font-semibold text-accent"
                      : "hover:bg-slate-50"
                  }`}
                >
                  <span className="block truncate">{kb.name}</span>
                  <span className="mt-0.5 block text-xs text-slate-500">
                    {kb.document_count} document{kb.document_count === 1 ? "" : "s"}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </aside>

        <section className="space-y-4">
          {!selectedKb ? (
            <p className="rounded-2xl border border-dashed border-slate-300 bg-white/50 px-4 py-10 text-center text-slate-500">
              Create a knowledge base to start uploading documents.
            </p>
          ) : (
            <>
              <div className="rounded-2xl border border-slate-200 bg-white/80 p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <h2 className="font-display text-xl font-semibold">{selectedKb.name}</h2>
                    <p className="mt-1 text-sm text-slate-600">
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
                      className="rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-white hover:bg-teal-700 disabled:opacity-60"
                    >
                      {uploading ? "Uploading..." : "+ Upload Document"}
                    </button>
                  </div>
                </div>
                <p className="mt-2 text-xs text-slate-500">
                  Supported: PDF, DOCX, TXT (max 20 MB)
                </p>
              </div>

              <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_320px]">
                <div className="rounded-2xl border border-slate-200 bg-white/80">
                  <div className="border-b border-slate-200 px-4 py-3">
                    <h3 className="text-sm font-semibold text-slate-700">Documents</h3>
                  </div>
                  <ul className="divide-y divide-slate-100">
                    {documents.length === 0 && (
                      <li className="px-4 py-8 text-center text-sm text-slate-500">
                        No documents uploaded yet.
                      </li>
                    )}
                    {documents.map((doc) => (
                      <li key={doc.id}>
                        <button
                          onClick={() => setSelectedDocId(doc.id)}
                          className={`flex w-full items-start justify-between gap-3 px-4 py-3 text-left ${
                            selectedDocId === doc.id ? "bg-slate-50" : "hover:bg-slate-50/70"
                          }`}
                        >
                          <div className="min-w-0">
                            <p className="truncate text-sm font-medium text-slate-800">
                              {doc.filename}
                            </p>
                            <p className="mt-1 text-xs text-slate-500">
                              Chunks: {doc.chunk_count} · Embedding:{" "}
                              {doc.embedding_status === "generated" ? "Generated" : doc.embedding_status}
                            </p>
                            {doc.error_message && (
                              <p className="mt-1 text-xs text-red-600">{doc.error_message}</p>
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

                <aside className="rounded-2xl border border-slate-200 bg-white/80">
                  <div className="border-b border-slate-200 px-4 py-3">
                    <h3 className="text-sm font-semibold text-slate-700">Chunks</h3>
                    {selectedDoc && (
                      <p className="mt-1 truncate text-xs text-slate-500">{selectedDoc.filename}</p>
                    )}
                  </div>
                  <div className="max-h-[420px] space-y-2 overflow-y-auto p-3">
                    {!selectedDoc && (
                      <p className="px-1 py-4 text-sm text-slate-500">
                        Select a document to inspect chunks.
                      </p>
                    )}
                    {selectedDoc && selectedDoc.status !== "processed" && (
                      <p className="px-1 py-4 text-sm text-slate-500">
                        {selectedDoc.status === "processing"
                          ? "Processing document..."
                          : "Document is not ready yet."}
                      </p>
                    )}
                    {selectedDoc?.status === "processed" &&
                      chunks.map((chunk) => (
                        <article
                          key={chunk.id}
                          className="rounded-lg border border-slate-200 bg-slate-50 p-3"
                        >
                          <p className="text-xs font-semibold text-slate-500">
                            Chunk {chunk.chunk_index + 1}
                          </p>
                          <p className="mt-1 line-clamp-4 text-sm text-slate-700">
                            {chunk.content}
                          </p>
                        </article>
                      ))}
                  </div>
                  {selectedDoc && (
                    <div className="border-t border-slate-200 p-3">
                      <button
                        onClick={() => onDeleteDocument(selectedDoc.id)}
                        className="w-full rounded-lg border border-red-200 px-3 py-2 text-sm font-medium text-red-700 hover:bg-red-50"
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
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 px-4">
          <form
            onSubmit={onCreateKb}
            className="w-full max-w-lg rounded-2xl border border-slate-200 bg-white p-6 shadow-lg"
          >
            <h2 className="font-display text-xl font-semibold">New Knowledge Base</h2>
            <p className="mt-1 text-sm text-slate-600">
              Group related documents such as research papers or company docs.
            </p>
            <label className="mt-4 block text-sm">
              <span className="mb-1 block text-slate-600">Name</span>
              <input
                required
                value={kbForm.name}
                onChange={(e) => setKbForm((f) => ({ ...f, name: e.target.value }))}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 outline-none ring-accent focus:ring-2"
                placeholder="Research Papers"
              />
            </label>
            <label className="mt-3 block text-sm">
              <span className="mb-1 block text-slate-600">Description</span>
              <textarea
                value={kbForm.description}
                onChange={(e) => setKbForm((f) => ({ ...f, description: e.target.value }))}
                className="min-h-24 w-full rounded-lg border border-slate-300 px-3 py-2 outline-none ring-accent focus:ring-2"
                placeholder="Optional notes about this collection"
              />
            </label>
            <div className="mt-5 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setDialog(null)}
                className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium hover:bg-slate-50"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={saving}
                className="rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-white hover:bg-teal-700 disabled:opacity-60"
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
