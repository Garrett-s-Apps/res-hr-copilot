import { NextRequest, NextResponse } from "next/server";
import { mockSearchResults } from "@/lib/mock-data";
import type { SearchResult } from "@/types";

interface SearchRequestBody {
  query?: string;
  department?: string;
  docType?: string;
}

export async function POST(req: NextRequest) {
  const body = (await req.json()) as SearchRequestBody;
  const { query = "", department = "All", docType = "All" } = body;

  // Use Azure Cognitive Search if configured
  if (process.env.AZURE_SEARCH_ENDPOINT && process.env.AZURE_SEARCH_KEY) {
    try {
      const index = process.env.AZURE_SEARCH_INDEX ?? "res-hr-index";
      const url = `${process.env.AZURE_SEARCH_ENDPOINT}/indexes/${index}/docs/search?api-version=2023-11-01`;

      const azureBody: Record<string, unknown> = {
        search: query,
        top: 10,
        queryType: "semantic",
        semanticConfiguration: "default",
        queryLanguage: "en-US",
        select: "id,title,excerpt,department,docType,source,pageNumber,lastUpdated",
      };

      if (department !== "All") {
        azureBody.filter = `department eq '${department}'`;
      }

      const azureRes = await fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "api-key": process.env.AZURE_SEARCH_KEY,
        },
        body: JSON.stringify(azureBody),
      });

      if (azureRes.ok) {
        const data = await azureRes.json() as { value: SearchResult[] };
        return NextResponse.json({ results: data.value, source: "azure" });
      }
    } catch (err) {
      console.error("Azure Search error, falling back to mock:", err);
    }
  }

  // Mock mode — filter and score locally
  let results = [...mockSearchResults];

  if (department !== "All") {
    results = results.filter((r) => r.department === department);
  }
  if (docType !== "All") {
    results = results.filter((r) => r.docType === docType);
  }

  // Simple keyword relevance boost
  if (query) {
    const terms = query.toLowerCase().split(/\s+/);
    results = results
      .map((r) => {
        const text = `${r.title} ${r.excerpt} ${r.source}`.toLowerCase();
        const termMatches = terms.filter((t) => text.includes(t)).length;
        return { ...r, score: Math.min(1, r.score + termMatches * 0.02) };
      })
      .sort((a, b) => b.score - a.score);
  }

  return NextResponse.json({ results, source: "mock" });
}
