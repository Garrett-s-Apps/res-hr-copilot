"use client";

import { useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
import Link from "next/link";
import {
  ChevronRight,
  FileText,
  Download,
  Calendar,
  Building2,
  Tag,
  MessageSquare,
  ExternalLink,
} from "lucide-react";
import PageShell from "@/components/layout/PageShell";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { mockDocuments } from "@/lib/mock-data";
import { formatDate } from "@/lib/utils";

export default function DocPage() {
  const { id } = useParams<{ id: string }>();
  const searchParams = useSearchParams();
  const page = searchParams.get("page") ?? "1";

  const doc = mockDocuments.find((d) => d.id === id);
  const [chatQuery, setChatQuery] = useState<string | undefined>();

  if (!doc) {
    return (
      <PageShell>
        <div className="max-w-4xl mx-auto px-4 py-16 text-center">
          <FileText className="h-12 w-12 text-gray-300 mx-auto mb-4" />
          <h1 className="text-2xl font-bold text-navy mb-2">Document Not Found</h1>
          <p className="text-gray-500 mb-6">
            The document you&apos;re looking for doesn&apos;t exist or has been moved.
          </p>
          <Button asChild>
            <Link href="/">Return Home</Link>
          </Button>
        </div>
      </PageShell>
    );
  }

  return (
    <PageShell initialChatQuery={chatQuery}>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {/* Breadcrumb */}
        <nav className="flex items-center gap-1.5 text-sm text-gray-500 mb-5">
          <Link href="/" className="hover:text-navy transition-colors">Home</Link>
          <ChevronRight className="h-3.5 w-3.5" />
          <Link href={`/search?dept=${doc.department}`} className="hover:text-navy transition-colors">
            {doc.department}
          </Link>
          <ChevronRight className="h-3.5 w-3.5" />
          <span className="text-navy font-medium truncate max-w-[200px]">{doc.title}</span>
        </nav>

        <div className="flex flex-col lg:flex-row gap-6">
          {/* PDF Viewer */}
          <div className="flex-1 min-w-0">
            <div className="bg-white rounded-xl border shadow-sm overflow-hidden">
              {/* Doc header */}
              <div className="px-5 py-4 border-b flex items-center justify-between gap-3">
                <div className="flex items-center gap-3 min-w-0">
                  <div className="w-9 h-9 rounded-lg bg-navy/10 flex items-center justify-center flex-shrink-0">
                    <FileText className="h-5 w-5 text-navy" />
                  </div>
                  <div className="min-w-0">
                    <h1 className="font-semibold text-navy text-base truncate">{doc.title}</h1>
                    <p className="text-xs text-gray-500">
                      {doc.pageCount} pages &bull; {doc.fileSize}
                    </p>
                  </div>
                </div>
                <Button variant="outline" size="sm" className="flex-shrink-0 gap-1.5">
                  <Download className="h-4 w-4" />
                  Download
                </Button>
              </div>

              {/* PDF iframe placeholder */}
              <div className="relative bg-gray-100" style={{ height: "680px" }}>
                {/* In production this would be an actual PDF. Mock shows a styled placeholder. */}
                <div className="absolute inset-0 flex flex-col items-center justify-center text-center p-8">
                  <div className="bg-white rounded-2xl shadow-lg p-10 max-w-md w-full">
                    <FileText className="h-16 w-16 text-navy/30 mx-auto mb-4" />
                    <h2 className="text-xl font-bold text-navy mb-2">{doc.title}</h2>
                    <p className="text-gray-500 text-sm mb-4 leading-relaxed">{doc.description}</p>
                    <div className="bg-navy/5 rounded-lg p-3 text-left text-xs text-gray-600 mb-5">
                      <p className="font-medium text-navy mb-1">Currently viewing: Page {page}</p>
                      <p>In production, connect a real PDF URL to display the document here via an iframe or react-pdf.</p>
                    </div>
                    <Button asChild variant="outline" className="gap-2">
                      <a href={`#pdf-${doc.id}`}>
                        <ExternalLink className="h-4 w-4" />
                        Open Full Document
                      </a>
                    </Button>
                  </div>
                </div>
              </div>

              {/* Page navigation */}
              <div className="px-5 py-3 border-t flex items-center justify-between text-sm text-gray-500 bg-gray-50">
                <span>Page {page} of {doc.pageCount}</span>
                <div className="flex gap-2">
                  <Button variant="outline" size="sm" disabled={parseInt(page) <= 1}>
                    Previous
                  </Button>
                  <Button variant="outline" size="sm" disabled={parseInt(page) >= doc.pageCount}>
                    Next
                  </Button>
                </div>
              </div>
            </div>
          </div>

          {/* Sidebar */}
          <aside className="lg:w-72 flex-shrink-0 space-y-4">
            {/* Document info */}
            <div className="bg-white rounded-xl border shadow-sm p-5 space-y-4">
              <h2 className="font-semibold text-navy text-sm">Document Details</h2>
              <div className="space-y-3 text-sm">
                <div className="flex items-start gap-2.5 text-gray-600">
                  <Building2 className="h-4 w-4 text-gray-400 mt-0.5 flex-shrink-0" />
                  <div>
                    <p className="text-xs text-gray-400">Department</p>
                    <p className="font-medium text-navy">{doc.department}</p>
                  </div>
                </div>
                <div className="flex items-start gap-2.5 text-gray-600">
                  <FileText className="h-4 w-4 text-gray-400 mt-0.5 flex-shrink-0" />
                  <div>
                    <p className="text-xs text-gray-400">Category</p>
                    <p className="font-medium text-navy">{doc.category}</p>
                  </div>
                </div>
                <div className="flex items-start gap-2.5 text-gray-600">
                  <Calendar className="h-4 w-4 text-gray-400 mt-0.5 flex-shrink-0" />
                  <div>
                    <p className="text-xs text-gray-400">Last Updated</p>
                    <p className="font-medium text-navy">{formatDate(doc.lastUpdated)}</p>
                  </div>
                </div>
                <div className="flex items-start gap-2.5 text-gray-600">
                  <Tag className="h-4 w-4 text-gray-400 mt-0.5 flex-shrink-0" />
                  <div>
                    <p className="text-xs text-gray-400 mb-1.5">Tags</p>
                    <div className="flex flex-wrap gap-1">
                      {doc.tags.map((tag) => (
                        <Badge key={tag} variant="outline" className="text-xs px-2 py-0">
                          {tag}
                        </Badge>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Ask AI about this doc */}
            <div className="bg-navy rounded-xl p-5 text-white">
              <div className="flex items-center gap-2 mb-2">
                <MessageSquare className="h-5 w-5 text-gold" />
                <h2 className="font-semibold text-sm">Ask about this document</h2>
              </div>
              <p className="text-gray-300 text-xs leading-relaxed mb-4">
                Have questions about this document? Our AI assistant can help explain policies and find specific information.
              </p>
              <div className="space-y-2">
                {[
                  `Summarize ${doc.title}`,
                  `What are the key points in ${doc.title}?`,
                  `Who does ${doc.title} apply to?`,
                ].map((prompt) => (
                  <button
                    key={prompt}
                    onClick={() => setChatQuery(prompt)}
                    className="w-full text-left text-xs px-3 py-2 rounded-lg bg-white/10 hover:bg-white/20 transition-colors text-gray-200 line-clamp-1"
                  >
                    {prompt}
                  </button>
                ))}
              </div>
              <Button
                onClick={() => setChatQuery(`Tell me about the ${doc.title}`)}
                className="w-full mt-3 bg-gold text-navy hover:bg-gold-500 text-sm font-semibold"
              >
                Open HR Assistant
              </Button>
            </div>

            {/* Related docs */}
            <div className="bg-white rounded-xl border shadow-sm p-5">
              <h2 className="font-semibold text-navy text-sm mb-3">Related Documents</h2>
              <div className="space-y-2">
                {mockDocuments
                  .filter((d) => d.id !== doc.id && d.department === doc.department)
                  .slice(0, 3)
                  .map((related) => (
                    <Link
                      key={related.id}
                      href={`/docs/${related.id}`}
                      className="flex items-start gap-2 text-xs text-gray-600 hover:text-navy group"
                    >
                      <FileText className="h-3.5 w-3.5 text-gray-400 mt-0.5 flex-shrink-0 group-hover:text-navy" />
                      <span className="group-hover:underline leading-snug">{related.title}</span>
                    </Link>
                  ))}
              </div>
            </div>
          </aside>
        </div>
      </div>
    </PageShell>
  );
}
