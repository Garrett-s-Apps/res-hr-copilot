import { NextRequest, NextResponse } from "next/server";
import { getMockChatResponse } from "@/lib/mock-data";
import type { ChatMessage } from "@/types";

interface ChatRequestBody {
  message: string;
  history?: ChatMessage[];
}

export async function POST(req: NextRequest) {
  const body = (await req.json()) as ChatRequestBody;
  const { message, history = [] } = body;

  // Use Azure OpenAI if configured
  if (process.env.AZURE_OPENAI_ENDPOINT && process.env.AZURE_OPENAI_KEY) {
    try {
      const deployment = process.env.AZURE_OPENAI_DEPLOYMENT ?? "gpt-4o";
      const url = `${process.env.AZURE_OPENAI_ENDPOINT}/openai/deployments/${deployment}/chat/completions?api-version=2024-02-01`;

      const systemPrompt = `You are the HR assistant for RES LLC, an internal AI-powered knowledge base assistant.
Your role is to help employees find information about HR policies, benefits, time off, expenses, and company procedures.
Always be helpful, professional, and accurate. When citing information, mention the source document and page number.
If you don't know something, direct employees to contact HR at hr@res-llc.com or IT at it@res-llc.com.`;

      const messages = [
        { role: "system", content: systemPrompt },
        ...history.slice(-6).map((m) => ({ role: m.role, content: m.content })),
        { role: "user", content: message },
      ];

      const azureRes = await fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "api-key": process.env.AZURE_OPENAI_KEY,
        },
        body: JSON.stringify({ messages, max_tokens: 800, temperature: 0.3 }),
      });

      if (azureRes.ok) {
        const data = await azureRes.json() as {
          choices: Array<{ message: { content: string } }>;
        };
        const content = data.choices[0]?.message?.content ?? "";
        return NextResponse.json({ response: content, citations: [], source: "azure" });
      }
    } catch (err) {
      console.error("Azure OpenAI error, falling back to mock:", err);
    }
  }

  // Mock mode — keyword-matched responses with citations
  await new Promise((resolve) => setTimeout(resolve, 600)); // Simulate latency

  const { response, citations } = getMockChatResponse(message);
  return NextResponse.json({ response, citations, source: "mock" });
}
