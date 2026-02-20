"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { X, Send, Bot, User, FileText, Loader2, MessageSquare } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import type { ChatMessage, Citation } from "@/types";
import { cn } from "@/lib/utils";
import Link from "next/link";

interface ChatPanelProps {
  open: boolean;
  onClose: () => void;
  initialQuery?: string;
}

function CitationCard({ citation }: { citation: Citation }) {
  return (
    <Link
      href={`/docs/${citation.docId}?page=${citation.pageNumber}`}
      className="flex items-start gap-2 p-2 rounded border border-navy/20 bg-navy/5 hover:bg-navy/10 transition-colors text-xs group"
    >
      <FileText className="h-3.5 w-3.5 text-navy mt-0.5 flex-shrink-0" />
      <div className="min-w-0">
        <p className="font-medium text-navy group-hover:underline truncate">{citation.docTitle}</p>
        <p className="text-gray-500">Page {citation.pageNumber}</p>
        <p className="text-gray-600 line-clamp-2 mt-0.5">{citation.excerpt}</p>
      </div>
    </Link>
  );
}

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";
  return (
    <div className={cn("flex gap-2.5", isUser ? "flex-row-reverse" : "flex-row")}>
      <div
        className={cn(
          "w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 mt-1",
          isUser ? "bg-gold" : "bg-navy"
        )}
      >
        {isUser ? (
          <User className="h-4 w-4 text-navy" />
        ) : (
          <Bot className="h-4 w-4 text-white" />
        )}
      </div>
      <div className={cn("max-w-[80%] space-y-2", isUser ? "items-end flex flex-col" : "")}>
        <div
          className={cn(
            "rounded-2xl px-4 py-2.5 text-sm leading-relaxed",
            isUser
              ? "bg-navy text-white rounded-tr-sm"
              : "bg-gray-100 text-gray-900 rounded-tl-sm"
          )}
        >
          {/* Render markdown-lite: bold */}
          {message.content.split("\n").map((line, i) => {
            const parts = line.split(/(\*\*[^*]+\*\*)/g);
            return (
              <p key={i} className={i > 0 ? "mt-1" : ""}>
                {parts.map((part, j) =>
                  part.startsWith("**") && part.endsWith("**") ? (
                    <strong key={j}>{part.slice(2, -2)}</strong>
                  ) : (
                    part
                  )
                )}
              </p>
            );
          })}
        </div>
        {message.citations && message.citations.length > 0 && (
          <div className="space-y-1.5 w-full">
            <p className="text-xs text-gray-500 font-medium">Sources:</p>
            {message.citations.map((citation, i) => (
              <CitationCard key={i} citation={citation} />
            ))}
          </div>
        )}
        <p className="text-xs text-gray-400">
          {message.timestamp.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
        </p>
      </div>
    </div>
  );
}

export default function ChatPanel({ open, onClose, initialQuery }: ChatPanelProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "welcome",
      role: "assistant",
      content: "Hi! I'm RES AI, your company knowledge base assistant. I can help you find procedures, understand contracts, locate policies, and walk you through how-to guides.",
      timestamp: new Date(),
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const initialQuerySent = useRef(false);

  const sendMessage = useCallback(
    async (text: string) => {
      if (!text.trim() || loading) return;

      const userMessage: ChatMessage = {
        id: `user-${Date.now()}`,
        role: "user",
        content: text.trim(),
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, userMessage]);
      setInput("");
      setLoading(true);

      try {
        const res = await fetch("/api/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message: text.trim(), history: messages }),
        });
        const data = await res.json() as { response: string; citations: Citation[] };
        const assistantMessage: ChatMessage = {
          id: `assistant-${Date.now()}`,
          role: "assistant",
          content: data.response,
          citations: data.citations,
          timestamp: new Date(),
        };
        setMessages((prev) => [...prev, assistantMessage]);
      } catch {
        setMessages((prev) => [
          ...prev,
          {
            id: `error-${Date.now()}`,
            role: "assistant",
            content: "Sorry, I encountered an error. Please try again or contact the appropriate team directly.",
            timestamp: new Date(),
          },
        ]);
      } finally {
        setLoading(false);
      }
    },
    [loading, messages]
  );

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  useEffect(() => {
    if (open) {
      setTimeout(() => inputRef.current?.focus(), 100);
      if (initialQuery && !initialQuerySent.current) {
        initialQuerySent.current = true;
        void sendMessage(initialQuery);
      }
    }
  }, [open, initialQuery, sendMessage]);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    void sendMessage(input);
  }

  if (!open) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/30 z-40 md:hidden"
        onClick={onClose}
      />

      {/* Panel */}
      <div className="fixed right-0 top-0 h-full w-full sm:w-[420px] bg-white shadow-2xl z-50 flex flex-col">
        {/* Header */}
        <div className="bg-navy px-4 py-3 flex items-center justify-between flex-shrink-0">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-full bg-gold flex items-center justify-center">
              <Bot className="h-4 w-4 text-navy" />
            </div>
            <div>
              <p className="text-white font-semibold text-sm">RES AI</p>
              <div className="flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-green-400" />
                <span className="text-gray-300 text-xs">Online</span>
              </div>
            </div>
          </div>
          <Button variant="ghost" size="icon" onClick={onClose} className="text-white hover:bg-white/10">
            <X className="h-5 w-5" />
          </Button>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {messages.map((msg) => (
            <MessageBubble key={msg.id} message={msg} />
          ))}
          {loading && (
            <div className="flex gap-2.5">
              <div className="w-7 h-7 rounded-full bg-navy flex items-center justify-center flex-shrink-0">
                <Bot className="h-4 w-4 text-white" />
              </div>
              <div className="bg-gray-100 rounded-2xl rounded-tl-sm px-4 py-3 flex items-center gap-2">
                <Loader2 className="h-4 w-4 animate-spin text-gray-500" />
                <span className="text-sm text-gray-500">Searching documents...</span>
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {/* Suggested prompts */}
        {messages.length === 1 && (
          <div className="px-4 pb-2 flex flex-wrap gap-1.5">
            {[
              "How do I restart a server?",
              "What's the expense approval process?",
              "Where's the client onboarding SOP?",
            ].map((prompt) => (
              <button
                key={prompt}
                onClick={() => void sendMessage(prompt)}
                className="text-xs px-3 py-1.5 rounded-full border border-navy/30 text-navy hover:bg-navy hover:text-white transition-colors"
              >
                {prompt}
              </button>
            ))}
          </div>
        )}

        {/* Input */}
        <div className="border-t p-3 flex-shrink-0">
          <form onSubmit={handleSubmit} className="flex gap-2">
            <Input
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask about procedures, contracts, policies..."
              disabled={loading}
              className="flex-1"
            />
            <Button type="submit" disabled={loading || !input.trim()} size="icon" className="flex-shrink-0">
              <Send className="h-4 w-4" />
            </Button>
          </form>
          <p className="text-xs text-gray-400 mt-2 text-center">
            AI responses are based on official RES LLC documents.
          </p>
        </div>
      </div>
    </>
  );
}
