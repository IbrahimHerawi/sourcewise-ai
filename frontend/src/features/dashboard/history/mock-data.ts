import type { HistoryDocumentFilter, HistoryEntry } from "./types";

export const historyDocumentFilters = [
  { id: "all", label: "Filter by document" },
  { id: "q3-report", label: "Q3 Report" },
  { id: "authentication-api", label: "Authentication API" },
  { id: "neptune-launch", label: "Neptune Launch" },
  { id: "archived-documents", label: "Archived Documents" },
] as const satisfies readonly HistoryDocumentFilter[];

export const historyEntries = [
  {
    id: "q3-financial-highlights",
    documentId: "q3-report",
    question: "What were the key financial highlights from the Q3 report?",
    answer:
      "The Q3 report highlights a 15% increase in year-over-year revenue, primarily driven by strong growth in the cloud services division. Operating margins improved to 24% from 21% in the previous quarter. Additionally, the company announced a new share buyback program valued at $2 billion, citing confidence in future cash flow generation and overall financial stability across all global markets.",
    createdAt: "5 min ago",
    model: "llama3.2:1b",
    provider: "ollama",
    sourceCount: 3,
    sources: ["Q3 Financial Report", "Cloud Services Summary", "Investor Update"],
    isExpandable: true,
  },
  {
    id: "authentication-api-integration",
    documentId: "authentication-api",
    question: "How do I integrate the new authentication API?",
    answer:
      "To integrate the new authentication API, you need to first obtain an API key from the developer portal. Once you have the key, initialize the SDK with your credentials and use the auth.login() method. Ensure you handle the JWT token securely in your local storage.",
    createdAt: "2 hours ago",
    model: "gpt-4o",
    provider: "openai",
    sourceCount: 1,
    sources: ["Authentication API Guide"],
  },
  {
    id: "neptune-project-timeline",
    documentId: "neptune-launch",
    question: "Explain the project timeline for the Neptune launch.",
    answer:
      "The Neptune project is divided into four phases: Discovery, Development, Beta Testing, and Global Rollout. Discovery concluded in January. Development is currently 60% complete and is expected to wrap up by May. Beta testing with select partners will occur throughout June and July, with the final global rollout scheduled for the first week of September 2024.",
    createdAt: "Yesterday",
    model: "claude-3-sonnet",
    provider: "anthropic",
    sourceCount: 2,
    sources: ["Neptune Launch Plan", "Partner Beta Brief"],
    isExpandable: true,
  },
] as const satisfies readonly HistoryEntry[];

export const historyTotalCount = 47;
