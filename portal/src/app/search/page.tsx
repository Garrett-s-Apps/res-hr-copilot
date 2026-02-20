"use client";

import { useState, useEffect, useCallback, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { Search, Filter, FileText, Calendar, Building2, MessageSquare, ChevronDown } from "lucide-react";
import PageShell from "@/components/layout/PageShell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import type { SearchResult } from "@/types";
import { formatDate } from "@/lib/utils";

const DEPARTMENTS = ["All", "HR", "Operations", "Finance", "Legal"];
const DOC_TYPES = ["All", "Policy", "Benefits", "Reference", "IT", "Safety", "Compliance"];

export default function SearchPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-gray-50 flex items-center justify-center"><div className="text-gray-400">Loading search...</div></div>}>
      <SearchPageInner />
    </Suspense>
  );
}

function SearchPageInner() {
  const params = useSearchParams();
  const router = useRouter();
  const initialQ = params.get("q") ?? "";
  const initialDept = params.get("dept") ?? "All";

  const [query, setQuery] = useState(initialQ);
  const [inputValue, setInputValue] = useState(initialQ);
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [dept, setDept] = useState(initialDept);
  const [docType, setDocType] = useState("All");
  const [chatQuery, setChatQuery] = useState<string | undefined>();
  const [showFilters, setShowFilters] = useState(false);

  const doSearch = useCallback(async (q: string, department: string, type: string) => {
    setLoading(true);
    try {
      const res = await fetch("/api/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: q, department, docType: type }),
      });
      const data = await res.json() as { results: SearchResult[] };
      setResults(data.results);
    } catch {
      setResults([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (query || initialDept !== "All") {
      void doSearch(query, dept, docType);
    }
  }, [query, dept, docType, doSearch, initialDept]);

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    setQuery(inputValue);
    router.push(`/search?q=${encodeURIComponent(inputValue)}`);
  }

  const scoreColor = (score: number) => {
    if (score >= 0.9) return "text-green-600 bg-green-50";
    if (score >= 0.8) return "text-blue-600 bg-blue-50";
    return "text-gray-600 bg-gray-50";
  };

  return (
    <PageShell initialChatQuery={chatQuery}>
      {/* Search header */}
      <div className="bg-navy py-6 px-4">
        <div className="max-w-4xl mx-auto">
          <form onSubmit={handleSearch} className="flex gap-2">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
              <Input
                type="search"
                placeholder="Search HR documents..."
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                className="pl-10 bg-white h-11"
              />
            </div>
            <Button type="submit" className="bg-gold text-navy hover:bg-gold-500 h-11 px-6">
              Search
            </Button>
          </form>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <div className="flex flex-col lg:flex-row gap-6">
          {/* Filter sidebar */}
          <aside className="lg:w-56 flex-shrink-0">
            <div className="bg-white rounded-xl border shadow-sm p-4 sticky top-20">
              <button
                className="flex items-center justify-between w-full lg:hidden mb-3"
                onClick={() => setShowFilters(!showFilters)}
              >
                <span className="font-semibold text-navy flex items-center gap-2">
                  <Filter className="h-4 w-4" /> Filters
                </span>
                <ChevronDown className={`h-4 w-4 transition-transform ${showFilters ? "rotate-180" : ""}`} />
              </button>
              <div className={`space-y-5 ${showFilters ? "block" : "hidden lg:block"}`}>
                <div>
                  <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2 flex items-center gap-1.5">
                    <Building2 className="h-3.5 w-3.5" /> Department
                  </h3>
                  <div className="space-y-1">
                    {DEPARTMENTS.map((d) => (
                      <button
                        key={d}
                        onClick={() => setDept(d)}
                        className={`w-full text-left text-sm px-2.5 py-1.5 rounded-md transition-colors ${
                          dept === d
                            ? "bg-navy text-white font-medium"
                            : "text-gray-600 hover:bg-gray-50"
                        }`}
                      >
                        {d}
                      </button>
                    ))}
                  </div>
                </div>
                <div>
                  <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2 flex items-center gap-1.5">
                    <FileText className="h-3.5 w-3.5" /> Document Type
                  </h3>
                  <div className="space-y-1">
                    {DOC_TYPES.map((t) => (
                      <button
                        key={t}
                        onClick={() => setDocType(t)}
                        className={`w-full text-left text-sm px-2.5 py-1.5 rounded-md transition-colors ${
                          docType === t
                            ? "bg-navy text-white font-medium"
                            : "text-gray-600 hover:bg-gray-50"
                        }`}
                      >
                        {t}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </aside>

          {/* Results */}
          <div className="flex-1 min-w-0">
            {/* Results count */}
            <div className="flex items-center justify-between mb-4">
              <p className="text-sm text-gray-600">
                {loading
                  ? "Searching..."
                  : query
                  ? `${results.length} result${results.length !== 1 ? "s" : ""} for "${query}"`
                  : dept !== "All"
                  ? `${results.length} documents in ${dept}`
                  : "Enter a search query"}
              </p>
              {query && !loading && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setChatQuery(query)}
                  className="gap-1.5 text-navy border-navy hover:bg-navy hover:text-white"
                >
                  <MessageSquare className="h-3.5 w-3.5" />
                  Ask AI about this
                </Button>
              )}
            </div>

            {/* Loading skeleton */}
            {loading && (
              <div className="space-y-3">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="bg-white rounded-xl border p-5 animate-pulse">
                    <div className="h-4 bg-gray-200 rounded w-2/3 mb-3" />
                    <div className="h-3 bg-gray-100 rounded w-full mb-1.5" />
                    <div className="h-3 bg-gray-100 rounded w-4/5" />
                  </div>
                ))}
              </div>
            )}

            {/* Results list */}
            {!loading && results.length > 0 && (
              <div className="space-y-3">
                {results.map((result) => (
                  <div
                    key={result.id}
                    className="bg-white rounded-xl border shadow-sm p-5 hover:shadow-md transition-shadow"
                  >
                    <div className="flex items-start justify-between gap-3 mb-2">
                      <h3 className="font-semibold text-navy text-base leading-snug">{result.title}</h3>
                      <span className={`text-xs px-2 py-0.5 rounded-full font-medium flex-shrink-0 ${scoreColor(result.score)}`}>
                        {Math.round(result.score * 100)}% match
                      </span>
                    </div>
                    <p className="text-gray-600 text-sm leading-relaxed mb-3 line-clamp-3">{result.excerpt}</p>
                    <div className="flex flex-wrap items-center gap-3 text-xs text-gray-500">
                      <span className="flex items-center gap-1">
                        <FileText className="h-3.5 w-3.5" />
                        {result.source} — p.{result.pageNumber}
                      </span>
                      <Badge variant="outline" className="text-xs">{result.department}</Badge>
                      <Badge variant="outline" className="text-xs">{result.docType}</Badge>
                      <span className="flex items-center gap-1">
                        <Calendar className="h-3.5 w-3.5" />
                        {formatDate(result.lastUpdated)}
                      </span>
                    </div>
                    <div className="mt-3 flex gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        asChild
                        className="text-navy border-navy hover:bg-navy hover:text-white"
                      >
                        <a href={`/docs/${result.id.replace("sr-", "doc-0")}?page=${result.pageNumber}`}>
                          View Document
                        </a>
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setChatQuery(`Tell me more about: ${result.title}`)}
                        className="text-gray-600 hover:text-navy gap-1"
                      >
                        <MessageSquare className="h-3.5 w-3.5" />
                        Ask about this
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Empty state */}
            {!loading && results.length === 0 && (query || dept !== "All") && (
              <div className="bg-white rounded-xl border p-12 text-center">
                <Search className="h-10 w-10 text-gray-300 mx-auto mb-3" />
                <h3 className="font-semibold text-gray-700 mb-1">No results found</h3>
                <p className="text-gray-500 text-sm mb-4">
                  Try different keywords or ask the AI assistant.
                </p>
                <Button onClick={() => setChatQuery(query)} className="gap-2">
                  <MessageSquare className="h-4 w-4" />
                  Ask HR AI
                </Button>
              </div>
            )}
          </div>
        </div>
      </div>
    </PageShell>
  );
}
