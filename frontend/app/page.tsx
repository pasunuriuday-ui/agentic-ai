"use client";

import {
  ChangeEvent,
  FormEvent,
  KeyboardEvent,
  useEffect,
  useRef,
  useState,
} from "react";

interface QueryResponse {
  success: boolean;
  answer?: string;
  error?: string;
  retrieved_documents?: number;
  retrieval_scores?: number[];
}

interface UploadResponse {
  success: boolean;
  filename?: string;
  chunks?: number;
  error?: string;
}

interface Message {
  id: number;
  role: "user" | "assistant";
  content: string;
  documents?: number;
  scores?: number[];
  error?: boolean;
}

interface AttachedFile {
  name: string;
  size: number;
  status: "uploading" | "uploaded" | "error";
  chunks?: number;
  error?: string;
}

export default function Home() {
  const [query, setQuery] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [apiHealthy, setApiHealthy] = useState(false);
  const [attachedFile, setAttachedFile] =
    useState<AttachedFile | null>(null);

  const inputRef = useRef<HTMLInputElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    checkHealth();
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({
      behavior: "smooth",
    });
  }, [messages, loading]);

  async function checkHealth() {
    try {
      const response = await fetch(
        "http://localhost:8000/health"
      );

      setApiHealthy(response.ok);
    } catch {
      setApiHealthy(false);
    }
  }

  async function handleFileChange(
    event: ChangeEvent<HTMLInputElement>
  ) {
    const file = event.target.files?.[0];

    if (!file) {
      return;
    }

    const extension = file.name
      .split(".")
      .pop()
      ?.toLowerCase();

    if (
      extension !== "pdf" &&
      extension !== "txt"
    ) {
      setAttachedFile({
        name: file.name,
        size: file.size,
        status: "error",
        error:
          "Only PDF and TXT files are supported.",
      });

      event.target.value = "";
      return;
    }

    setAttachedFile({
      name: file.name,
      size: file.size,
      status: "uploading",
    });

    setUploading(true);

    const formData = new FormData();

    formData.append("file", file);

    try {
      const response = await fetch(
        "http://localhost:8000/upload",
        {
          method: "POST",
          body: formData,
        }
      );

      const data: UploadResponse =
        await response.json();

      if (!response.ok || !data.success) {
        throw new Error(
          data.error ||
            "File upload failed."
        );
      }

      setAttachedFile({
        name: data.filename || file.name,
        size: file.size,
        status: "uploaded",
        chunks: data.chunks,
      });

      setApiHealthy(true);

      setTimeout(() => {
        inputRef.current?.focus();
      }, 100);
    } catch (error) {
      setAttachedFile({
        name: file.name,
        size: file.size,
        status: "error",
        error:
          error instanceof Error
            ? error.message
            : "File upload failed.",
      });
    } finally {
      setUploading(false);

      event.target.value = "";
    }
  }

  function removeFile() {
    setAttachedFile(null);

    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }

    inputRef.current?.focus();
  }

  async function askQuestion(
    event?: FormEvent<HTMLFormElement>
  ) {
    event?.preventDefault();

    const question = query.trim();

    if (!question || loading || uploading) {
      return;
    }

    const userMessage: Message = {
      id: Date.now(),
      role: "user",
      content: question,
    };

    setMessages((current) => [
      ...current,
      userMessage,
    ]);

    setQuery("");
    setLoading(true);

    try {
      const response = await fetch(
        "http://localhost:8000/query",
        {
          method: "POST",
          headers: {
            "Content-Type":
              "application/json",
          },
          body: JSON.stringify({
            query: question,
          }),
        }
      );

      const data: QueryResponse =
        await response.json();

      if (data.success) {
        const assistantMessage: Message = {
          id: Date.now() + 1,
          role: "assistant",
          content:
            data.answer ??
            "No answer returned.",
          documents:
            data.retrieved_documents,
          scores:
            data.retrieval_scores,
        };

        setMessages((current) => [
          ...current,
          assistantMessage,
        ]);

        setApiHealthy(true);
      } else {
        const refusalMessage: Message = {
          id: Date.now() + 1,
          role: "assistant",
          content:
            data.error ??
            "No relevant information found.",
          error: true,
        };

        setMessages((current) => [
          ...current,
          refusalMessage,
        ]);

        setApiHealthy(true);
      }
    } catch {
      const connectionMessage: Message = {
        id: Date.now() + 1,
        role: "assistant",
        content:
          "Unable to connect to the AI backend. Please make sure the FastAPI service is running.",
        error: true,
      };

      setMessages((current) => [
        ...current,
        connectionMessage,
      ]);

      setApiHealthy(false);
    } finally {
      setLoading(false);

      setTimeout(() => {
        inputRef.current?.focus();
      }, 50);
    }
  }

  function handleInputKeyDown(
    event: KeyboardEvent<HTMLInputElement>
  ) {
    if (
      event.key === "Enter" &&
      !event.shiftKey
    ) {
      event.preventDefault();

      if (
        query.trim() &&
        !loading &&
        !uploading
      ) {
        askQuestion();
      }
    }
  }

  function clearChat() {
    setMessages([]);
    setQuery("");
    setAttachedFile(null);

    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }

    setTimeout(() => {
      inputRef.current?.focus();
    }, 50);
  }

  function formatFileSize(
    bytes: number
  ) {
    if (bytes < 1024) {
      return `${bytes} B`;
    }

    if (bytes < 1024 * 1024) {
      return `${(bytes / 1024).toFixed(1)} KB`;
    }

    return `${(
      bytes /
      (1024 * 1024)
    ).toFixed(1)} MB`;
  }

  return (
    <main className="min-h-screen bg-[#07090d] text-white selection:bg-cyan-400/30">
      {/* Background */}
      <div className="pointer-events-none fixed inset-0 overflow-hidden">
        <div className="absolute left-1/2 top-[-240px] h-[500px] w-[800px] -translate-x-1/2 rounded-full bg-cyan-500/10 blur-[140px]" />

        <div className="absolute bottom-[-300px] left-[-150px] h-[500px] w-[500px] rounded-full bg-blue-600/10 blur-[140px]" />
      </div>

      <div className="relative mx-auto flex min-h-screen w-full max-w-6xl flex-col">
        {/* Header */}
        <header className="sticky top-0 z-20 border-b border-white/[0.06] bg-[#07090d]/85 backdrop-blur-xl">
          <div className="flex h-[72px] items-center justify-between px-5 sm:px-8">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-cyan-400/20 bg-cyan-400/10 text-xl shadow-[0_0_30px_rgba(34,211,238,0.08)]">
                ✦
              </div>

              <div>
                <div className="text-[17px] font-semibold tracking-tight">
                  NEXA RAG
                </div>

                <div className="text-[11px] tracking-wide text-slate-500">
                  INTELLIGENT KNOWLEDGE SYSTEM
                </div>
              </div>
            </div>

            <div className="flex items-center gap-3">
              <div className="hidden rounded-full border border-white/[0.07] bg-white/[0.025] px-3 py-1.5 text-[11px] text-slate-400 sm:block">
                RAG ENGINE
              </div>

              <div className="flex items-center gap-2 rounded-full border border-white/[0.07] bg-white/[0.025] px-3 py-1.5">
                <span
                  className={`h-2 w-2 rounded-full ${
                    apiHealthy
                      ? "bg-emerald-400 shadow-[0_0_10px_rgba(52,211,153,0.8)]"
                      : "bg-red-400 shadow-[0_0_10px_rgba(248,113,113,0.6)]"
                  }`}
                />

                <span className="text-[11px] text-slate-400">
                  {apiHealthy
                    ? "ONLINE"
                    : "OFFLINE"}
                </span>
              </div>
            </div>
          </div>
        </header>

        {/* Main */}
        <section className="flex flex-1 flex-col px-4 pb-5 pt-6 sm:px-8 sm:pt-8">
          {/* Welcome */}
          {messages.length === 0 &&
            !loading && (
              <div className="flex flex-1 items-center justify-center py-16">
                <div className="w-full max-w-3xl text-center">
                  <div className="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-2xl border border-cyan-400/20 bg-cyan-400/10 text-3xl shadow-[0_0_50px_rgba(34,211,238,0.08)]">
                    ✦
                  </div>

                  <p className="mb-3 text-xs font-medium uppercase tracking-[0.28em] text-cyan-400/80">
                    Grounded Intelligence
                  </p>

                  <h1 className="text-4xl font-semibold tracking-[-0.03em] text-white sm:text-5xl">
                    Ask your knowledge.
                  </h1>

                  <p className="mx-auto mt-5 max-w-xl text-sm leading-7 text-slate-500 sm:text-base">
                    Ask a question or upload a
                    document. NEXA retrieves
                    relevant knowledge before
                    generating a grounded response.
                  </p>

                  <div className="mx-auto mt-8 grid max-w-2xl gap-2 sm:grid-cols-2">
                    {[
                      "How does Qdrant store vectors?",
                      "What is machine learning?",
                      "What is FastAPI?",
                      "What is RAG?",
                    ].map(
                      (suggestion) => (
                        <button
                          key={suggestion}
                          type="button"
                          onClick={() => {
                            setQuery(
                              suggestion
                            );

                            inputRef.current?.focus();
                          }}
                          className="rounded-xl border border-white/[0.07] bg-white/[0.025] px-4 py-3 text-left text-sm text-slate-400 transition hover:border-cyan-400/20 hover:bg-cyan-400/[0.04] hover:text-white"
                        >
                          {suggestion}
                        </button>
                      )
                    )}
                  </div>
                </div>
              </div>
            )}

          {/* Chat */}
          {messages.length > 0 && (
            <div className="mx-auto w-full max-w-4xl flex-1 space-y-7 pb-8">
              {messages.map(
                (message) => (
                  <div key={message.id}>
                    {message.role ===
                    "user" ? (
                      <div className="flex justify-end">
                        <div className="max-w-[85%] rounded-2xl rounded-br-md bg-white px-4 py-3 text-sm leading-6 text-slate-900 shadow-lg shadow-black/10 sm:max-w-[75%]">
                          {message.content}
                        </div>
                      </div>
                    ) : (
                      <div className="flex gap-3">
                        <div
                          className={`mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border text-sm ${
                            message.error
                              ? "border-amber-400/20 bg-amber-400/10 text-amber-400"
                              : "border-cyan-400/20 bg-cyan-400/10 text-cyan-400"
                          }`}
                        >
                          {message.error
                            ? "!"
                            : "✦"}
                        </div>

                        <div className="min-w-0 flex-1">
                          <div className="mb-2 text-xs font-medium text-slate-500">
                            {message.error
                              ? "SYSTEM"
                              : "NEXA"}
                          </div>

                          <div
                            className={`rounded-2xl rounded-tl-md border px-5 py-4 ${
                              message.error
                                ? "border-amber-400/10 bg-amber-400/[0.04]"
                                : "border-white/[0.07] bg-white/[0.025]"
                            }`}
                          >
                            <p
                              className={`whitespace-pre-wrap text-sm leading-7 ${
                                message.error
                                  ? "text-amber-200/80"
                                  : "text-slate-200"
                              }`}
                            >
                              {
                                message.content
                              }
                            </p>

                            {!message.error &&
                              message.documents !==
                                undefined && (
                                <div className="mt-5 border-t border-white/[0.06] pt-4">
                                  <div className="mb-3 flex items-center justify-between">
                                    <span className="text-[10px] font-semibold uppercase tracking-[0.2em] text-slate-600">
                                      Retrieval
                                    </span>

                                    <span className="text-[10px] text-slate-600">
                                      {
                                        message.documents
                                      }{" "}
                                      documents
                                    </span>
                                  </div>

                                  <div className="flex flex-wrap gap-2">
                                    {message.scores?.map(
                                      (
                                        score,
                                        index
                                      ) => (
                                        <div
                                          key={`${message.id}-${index}`}
                                          className="rounded-lg border border-white/[0.06] bg-black/20 px-3 py-2"
                                        >
                                          <div className="text-[9px] uppercase tracking-wider text-slate-600">
                                            Match{" "}
                                            {index +
                                              1}
                                          </div>

                                          <div className="mt-0.5 text-xs font-medium text-cyan-400">
                                            {score.toFixed(
                                              3
                                            )}
                                          </div>
                                        </div>
                                      )
                                    )}
                                  </div>
                                </div>
                              )}
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                )
              )}

              {/* Loading */}
              {loading && (
                <div className="flex gap-3">
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-cyan-400/20 bg-cyan-400/10 text-sm text-cyan-400">
                    ✦
                  </div>

                  <div>
                    <div className="mb-2 text-xs font-medium text-slate-500">
                      NEXA
                    </div>

                    <div className="rounded-2xl rounded-tl-md border border-white/[0.07] bg-white/[0.025] px-5 py-4">
                      <div className="flex items-center gap-2">
                        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-cyan-400" />

                        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-cyan-400 [animation-delay:150ms]" />

                        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-cyan-400 [animation-delay:300ms]" />

                        <span className="ml-2 text-xs text-slate-500">
                          Retrieving
                          knowledge...
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              <div ref={bottomRef} />
            </div>
          )}

          {/* Composer */}
          <div className="sticky bottom-0 mx-auto w-full max-w-4xl bg-gradient-to-t from-[#07090d] via-[#07090d] to-transparent pb-1 pt-5">
            {/* Uploaded file */}
            {attachedFile && (
              <div className="mb-3 flex items-center justify-between rounded-xl border border-white/[0.07] bg-[#0d1118]/95 px-3 py-3 backdrop-blur-xl">
                <div className="flex min-w-0 items-center gap-3">
                  <div
                    className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-lg ${
                      attachedFile.status ===
                      "error"
                        ? "bg-red-400/10 text-red-400"
                        : "bg-cyan-400/10 text-cyan-400"
                    }`}
                  >
                    {attachedFile.name
                      .toLowerCase()
                      .endsWith(".pdf")
                      ? "PDF"
                      : "TXT"}
                  </div>

                  <div className="min-w-0">
                    <div className="truncate text-sm text-slate-200">
                      {attachedFile.name}
                    </div>

                    <div className="mt-0.5 text-[10px] text-slate-600">
                      {attachedFile.status ===
                        "uploading" &&
                        "Uploading and indexing..."}

                      {attachedFile.status ===
                        "uploaded" &&
                        `${formatFileSize(
                          attachedFile.size
                        )} • ${
                          attachedFile.chunks
                        } chunks indexed`}

                      {attachedFile.status ===
                        "error" &&
                        attachedFile.error}
                    </div>
                  </div>
                </div>

                <button
                  type="button"
                  onClick={removeFile}
                  className="ml-3 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-slate-600 transition hover:bg-white/[0.05] hover:text-white"
                  aria-label="Remove file"
                >
                  ×
                </button>
              </div>
            )}

            <form onSubmit={askQuestion}>
              <div className="group flex items-center gap-2 rounded-2xl border border-white/[0.09] bg-[#0d1118]/95 p-2 shadow-[0_20px_60px_rgba(0,0,0,0.35)] backdrop-blur-xl transition focus-within:border-cyan-400/30">
                {/* Hidden file input */}
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".pdf,.txt,application/pdf,text/plain"
                  onChange={
                    handleFileChange
                  }
                  className="hidden"
                />

                {/* Attach button */}
                <button
                  type="button"
                  disabled={
                    uploading ||
                    loading
                  }
                  onClick={() =>
                    fileInputRef.current?.click()
                  }
                  className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl text-lg text-slate-500 transition hover:bg-white/[0.05] hover:text-cyan-400 disabled:cursor-not-allowed disabled:opacity-30"
                  aria-label="Attach PDF or TXT"
                  title="Attach PDF or TXT"
                >
                  📎
                </button>

                <input
                  ref={inputRef}
                  value={query}
                  onChange={(event) =>
                    setQuery(
                      event.target.value
                    )
                  }
                  onKeyDown={
                    handleInputKeyDown
                  }
                  disabled={
                    loading ||
                    uploading
                  }
                  autoComplete="off"
                  placeholder={
                    uploading
                      ? "Indexing document..."
                      : "Ask NEXA anything from your knowledge base..."
                  }
                  className="min-w-0 flex-1 bg-transparent px-2 py-3 text-sm text-white outline-none placeholder:text-slate-600"
                />

                <button
                  type="submit"
                  disabled={
                    !query.trim() ||
                    loading ||
                    uploading
                  }
                  className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-white text-lg text-slate-950 transition hover:bg-cyan-300 disabled:cursor-not-allowed disabled:opacity-30"
                  aria-label="Send question"
                >
                  ↑
                </button>
              </div>
            </form>

            <div className="mt-3 flex items-center justify-between px-1">
              <div className="text-[10px] text-slate-700">
                📎 PDF / TXT&nbsp;&nbsp; • &nbsp;&nbsp;
                ENTER TO SEND&nbsp;&nbsp; • &nbsp;&nbsp;
                GROUNDED RAG
              </div>

              <button
                type="button"
                onClick={clearChat}
                disabled={
                  messages.length === 0 &&
                  !attachedFile
                }
                className="text-[10px] text-slate-600 transition hover:text-slate-300 disabled:opacity-30"
              >
                CLEAR CHAT
              </button>
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}