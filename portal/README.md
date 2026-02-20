# RES Connect — HR Intranet Portal

AI-powered HR knowledge base for RES LLC employees. Built with Next.js 14 (App Router), TypeScript, Tailwind CSS, and shadcn/ui.

## Features

- **Homepage** — Announcements, quick links, department sections
- **Semantic Search** — Full-text search with department/type filters
- **AI Chat Panel** — Slide-out chat with document citations
- **Document Viewer** — PDF viewer with sidebar navigation
- **Mock Mode** — Works out of the box without Azure credentials

## Tech Stack

- Next.js 14 (App Router)
- TypeScript (strict)
- Tailwind CSS
- shadcn/ui components (Radix UI primitives)
- Azure Cognitive Search (optional)
- Azure OpenAI (optional)

## Quick Start

```bash
cd portal
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) — works in mock mode with no env vars required.

## Environment Variables

Copy `.env.local.example` to `.env.local` and fill in your Azure credentials:

```bash
cp .env.local.example .env.local
```

| Variable | Description | Required |
|---|---|---|
| `AZURE_SEARCH_ENDPOINT` | Azure Cognitive Search endpoint URL | No (mock mode) |
| `AZURE_SEARCH_KEY` | Azure Search admin key | No |
| `AZURE_SEARCH_INDEX` | Search index name | No (default: `res-hr-index`) |
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI endpoint URL | No (mock mode) |
| `AZURE_OPENAI_KEY` | Azure OpenAI API key | No |
| `AZURE_OPENAI_DEPLOYMENT` | Model deployment name | No (default: `gpt-4o`) |
| `NEXT_PUBLIC_COMPANY_NAME` | Displayed company name | No (default: `RES, LLC`) |
| `NEXT_PUBLIC_SUPPORT_EMAIL` | IT support email shown in footer | No (default: `it@res-llc.com`) |

## Mock Mode

When Azure credentials are not set, all API routes return realistic mock data:

- `/api/search` — Returns 4 mock HR search results with relevance scoring
- `/api/chat` — Returns keyword-matched responses with source citations

## Deployment (Vercel)

```bash
vercel --prod
```

Set the environment variables in the Vercel dashboard or via `vercel env add`. The `vercel.json` is pre-configured for Next.js.

## Project Structure

```
portal/
  src/
    app/
      page.tsx              # Homepage
      search/page.tsx       # Search results
      docs/[id]/page.tsx    # Document viewer
      api/
        search/route.ts     # Search API (Azure or mock)
        chat/route.ts       # Chat API (Azure OpenAI or mock)
    components/
      layout/
        Navbar.tsx          # Top navigation with search
        Footer.tsx          # Footer with IT contact
        PageShell.tsx       # Shared layout wrapper + chat panel
      chat/
        ChatPanel.tsx       # Slide-out AI chat panel
      ui/                   # shadcn/ui base components
    lib/
      mock-data.ts          # Mock documents, announcements, chat responses
      utils.ts              # cn(), formatDate(), truncate()
    types/
      index.ts              # Shared TypeScript interfaces
```

## Azure Search Index Schema

If connecting to Azure Cognitive Search, create an index with these fields:

```json
{
  "name": "res-hr-index",
  "fields": [
    { "name": "id", "type": "Edm.String", "key": true },
    { "name": "title", "type": "Edm.String", "searchable": true },
    { "name": "excerpt", "type": "Edm.String", "searchable": true },
    { "name": "department", "type": "Edm.String", "filterable": true, "facetable": true },
    { "name": "docType", "type": "Edm.String", "filterable": true, "facetable": true },
    { "name": "source", "type": "Edm.String", "searchable": true },
    { "name": "pageNumber", "type": "Edm.Int32" },
    { "name": "lastUpdated", "type": "Edm.DateTimeOffset", "filterable": true, "sortable": true }
  ]
}
```

## License

Internal use only — RES LLC &copy; 2024
