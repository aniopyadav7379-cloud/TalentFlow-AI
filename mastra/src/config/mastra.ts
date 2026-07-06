import "dotenv/config";

function required(name: string, fallback?: string): string {
  const value = process.env[name] ?? fallback;
  if (value === undefined) {
    throw new Error(`Missing required environment variable: ${name}`);
  }
  return value;
}

export const config = {
  backendBaseUrl: required("BACKEND_BASE_URL", "http://localhost:8000/api/v1"),
  model: required("MASTRA_MODEL", "openai/gpt-4o-mini"),
  openaiApiKey: process.env.OPENAI_API_KEY ?? "",
  huggingfaceApiKey: process.env.HUGGINGFACE_API_KEY ?? "",
  qdrantUrl: required("QDRANT_URL", "http://localhost:6333"),
  qdrantApiKey: process.env.QDRANT_API_KEY ?? undefined,
  memoryCollection: required("MASTRA_MEMORY_COLLECTION", "mastra_memory"),
  port: Number(process.env.PORT ?? "4111"),
  corsOrigins: (process.env.CORS_ORIGINS ?? "http://localhost:3000")
    .split(",")
    .map((origin) => origin.trim())
    .filter(Boolean),
} as const;