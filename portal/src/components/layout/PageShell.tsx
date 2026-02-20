"use client";

import { useState } from "react";
import Navbar from "./Navbar";
import Footer from "./Footer";
import ChatPanel from "@/components/chat/ChatPanel";
import { MessageSquare } from "lucide-react";

interface PageShellProps {
  children: React.ReactNode;
  initialChatQuery?: string;
}

export default function PageShell({ children, initialChatQuery }: PageShellProps) {
  const [chatOpen, setChatOpen] = useState(false);

  return (
    <div className="min-h-screen flex flex-col bg-gray-50">
      <Navbar onOpenChat={() => setChatOpen(true)} />
      <main className="flex-1">{children}</main>
      <Footer />

      {/* Floating Ask HR button */}
      <button
        onClick={() => setChatOpen(true)}
        className="fixed bottom-6 right-6 bg-navy text-white rounded-full shadow-lg px-4 py-3 flex items-center gap-2 hover:bg-navy-600 transition-all hover:scale-105 z-30 text-sm font-medium"
      >
        <MessageSquare className="h-4 w-4" />
        Ask HR
      </button>

      <ChatPanel
        open={chatOpen}
        onClose={() => setChatOpen(false)}
        initialQuery={initialChatQuery}
      />
    </div>
  );
}
