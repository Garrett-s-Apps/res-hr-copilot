"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  Search,
  Monitor,
  Users,
  DollarSign,
  ChevronRight,
  FileText,
  Bell,
  BookOpen,
  Briefcase,
  Shield,
  Building2,
} from "lucide-react";
import PageShell from "@/components/layout/PageShell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { mockAnnouncements, mockDocuments } from "@/lib/mock-data";
import { formatDate } from "@/lib/utils";

const quickLinks = [
  { label: "IT Help", icon: Monitor, href: "/docs/doc-001", color: "bg-purple-50 text-purple-700 border-purple-200" },
  { label: "Procedures", icon: BookOpen, href: "/docs/doc-006", color: "bg-blue-50 text-blue-700 border-blue-200" },
  { label: "Contracts", icon: FileText, href: "/docs/doc-002", color: "bg-rose-50 text-rose-700 border-rose-200" },
  { label: "Finance", icon: DollarSign, href: "/docs/doc-004", color: "bg-green-50 text-green-700 border-green-200" },
  { label: "Projects", icon: Briefcase, href: "/docs/doc-003", color: "bg-amber-50 text-amber-700 border-amber-200" },
  { label: "Policies", icon: Shield, href: "/docs/doc-008", color: "bg-teal-50 text-teal-700 border-teal-200" },
];

const departments = [
  { id: "IT", name: "IT & Systems", icon: Monitor, color: "border-l-purple-500", docs: mockDocuments.filter((d) => d.department === "IT") },
  { id: "Operations", name: "Operations & SOPs", icon: Briefcase, color: "border-l-blue-500", docs: mockDocuments.filter((d) => d.department === "Operations") },
  { id: "Legal", name: "Legal & Contracts", icon: FileText, color: "border-l-red-500", docs: mockDocuments.filter((d) => d.department === "Legal") },
  { id: "Finance", name: "Finance & Controls", icon: DollarSign, color: "border-l-green-500", docs: mockDocuments.filter((d) => d.department === "Finance") },
];

export default function HomePage() {
  const router = useRouter();
  const [heroQuery, setHeroQuery] = useState("");
  const [chatQuery, setChatQuery] = useState<string | undefined>();

  function handleHeroSearch(e: React.FormEvent) {
    e.preventDefault();
    if (heroQuery.trim()) {
      router.push(`/search?q=${encodeURIComponent(heroQuery.trim())}`);
    }
  }

  function handleAskAI() {
    if (heroQuery.trim()) {
      setChatQuery(heroQuery.trim());
    }
  }

  return (
    <PageShell initialChatQuery={chatQuery}>
      {/* Hero */}
      <section className="bg-gradient-to-br from-navy via-navy-700 to-navy-800 text-white py-16 px-4">
        <div className="max-w-3xl mx-auto text-center">
          <div className="inline-flex items-center gap-2 bg-gold/20 text-gold px-3 py-1 rounded-full text-sm font-medium mb-4">
            <span className="w-2 h-2 rounded-full bg-gold" />
            AI-Powered Knowledge Base
          </div>
          <h1 className="text-4xl sm:text-5xl font-bold mb-3 leading-tight">
            Welcome to{" "}
            <span className="text-gold">RES Connect</span>
          </h1>
          <p className="text-gray-300 text-lg mb-8">
            Find company procedures, contracts, policies, and how-to guides — instantly.
          </p>
          <form onSubmit={handleHeroSearch} className="flex flex-col sm:flex-row gap-3 max-w-xl mx-auto">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-gray-400" />
              <Input
                type="search"
                placeholder="Ask anything — &ldquo;How do I submit an expense report?&rdquo;"
                value={heroQuery}
                onChange={(e) => setHeroQuery(e.target.value)}
                className="pl-10 h-12 text-base bg-white text-gray-900 border-0 w-full"
              />
            </div>
            <div className="flex gap-2">
              <Button type="submit" size="lg" className="bg-gold text-navy hover:bg-gold-500 font-semibold px-6">
                Search
              </Button>
              <Button
                type="button"
                size="lg"
                variant="outline"
                onClick={handleAskAI}
                className="border-white/30 text-white hover:bg-white/10 px-4"
              >
                Ask AI
              </Button>
            </div>
          </form>
        </div>
      </section>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 space-y-12">
        {/* Announcements */}
        <section>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-bold text-navy flex items-center gap-2">
              <Bell className="h-5 w-5 text-gold" />
              Announcements
            </h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {mockAnnouncements.map((ann) => (
              <div
                key={ann.id}
                className="bg-white rounded-xl border shadow-sm p-5 hover:shadow-md transition-shadow flex flex-col gap-3"
              >
                <div className="flex items-start justify-between gap-2">
                  <Badge variant={ann.urgent ? "destructive" : "secondary"} className="text-xs">
                    {ann.urgent ? "Urgent" : ann.category}
                  </Badge>
                  <span className="text-xs text-gray-400 flex-shrink-0">{formatDate(ann.date)}</span>
                </div>
                <h3 className="font-semibold text-navy text-sm leading-snug">{ann.title}</h3>
                <p className="text-gray-600 text-sm leading-relaxed line-clamp-3">{ann.body}</p>
                <p className="text-xs text-gray-400 mt-auto">{ann.author}</p>
              </div>
            ))}
          </div>
        </section>

        {/* Quick Links */}
        <section>
          <h2 className="text-xl font-bold text-navy mb-4">Quick Links</h2>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
            {quickLinks.map((link) => {
              const Icon = link.icon;
              return (
                <Link
                  key={link.href}
                  href={link.href}
                  className={`flex flex-col items-center gap-2 p-4 rounded-xl border bg-white hover:shadow-md transition-all hover:-translate-y-0.5 text-center ${link.color}`}
                >
                  <Icon className="h-7 w-7" />
                  <span className="text-sm font-medium">{link.label}</span>
                </Link>
              );
            })}
          </div>
        </section>

        {/* Departments */}
        <section>
          <h2 className="text-xl font-bold text-navy mb-4">Departments</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {departments.map((dept) => {
              const Icon = dept.icon;
              return (
                <div
                  key={dept.id}
                  className={`bg-white rounded-xl border border-l-4 ${dept.color} shadow-sm p-5 hover:shadow-md transition-shadow`}
                >
                  <div className="flex items-center gap-3 mb-3">
                    <Icon className="h-6 w-6 text-navy" />
                    <div>
                      <h3 className="font-semibold text-navy text-sm">{dept.name}</h3>
                      <p className="text-xs text-gray-500">{dept.docs.length} documents</p>
                    </div>
                  </div>
                  <ul className="space-y-1.5">
                    {dept.docs.slice(0, 3).map((doc) => (
                      <li key={doc.id}>
                        <Link
                          href={`/docs/${doc.id}`}
                          className="flex items-center gap-1.5 text-xs text-gray-600 hover:text-navy hover:underline"
                        >
                          <FileText className="h-3 w-3 flex-shrink-0" />
                          <span className="truncate">{doc.title}</span>
                        </Link>
                      </li>
                    ))}
                  </ul>
                  {dept.docs.length > 3 && (
                    <Link
                      href={`/search?dept=${dept.id}`}
                      className="mt-3 flex items-center gap-1 text-xs text-navy font-medium hover:underline"
                    >
                      View all <ChevronRight className="h-3 w-3" />
                    </Link>
                  )}
                </div>
              );
            })}
          </div>
        </section>
      </div>
    </PageShell>
  );
}
