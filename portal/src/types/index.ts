export interface Document {
  id: string;
  title: string;
  department: string;
  category: string;
  description: string;
  fileSize: string;
  lastUpdated: string;
  pageCount: number;
  tags: string[];
}

export interface SearchResult {
  id: string;
  title: string;
  excerpt: string;
  department: string;
  docType: string;
  source: string;
  pageNumber: number;
  lastUpdated: string;
  score: number;
}

export interface Announcement {
  id: string;
  title: string;
  body: string;
  author: string;
  date: string;
  category: string;
  urgent: boolean;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  timestamp: Date;
}

export interface Citation {
  docId: string;
  docTitle: string;
  pageNumber: number;
  excerpt: string;
}

export interface QuickLink {
  id: string;
  label: string;
  description: string;
  icon: string;
  href: string;
  color: string;
}

export interface Department {
  id: string;
  name: string;
  docCount: number;
  description: string;
  icon: string;
}
