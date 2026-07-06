/**
 * Agent memory, backed by the SAME Qdrant deployment the Python backend
 * already uses — a dedicated `mastra_memory` collection, not a second
 * vector database. Deliberately a small custom module rather than Mastra's
 * built-in Memory class: this codebase hasn't verified that class's exact
 * storage-adapter wiring closely enough to depend on it for a hackathon
 * deadline, whereas this module is straightforward, testable, and does
 * exactly what's asked (remember recruiter preferences/searches/candidates)
 * with a real, working Qdrant client. Swapping this for Mastra's official
 * Memory primitive later is a contained change — everything else only
 * calls `remember()`/`recall()`.
 */
import { QdrantClient } from "@qdrant/js-client-rest";

import { config } from "../config/mastra.js";

export type MemoryType = "search" | "candidate_interaction" | "preference";

export interface MemoryRecord {
  recruiterId: string;
  type: MemoryType;
  text: string;
  metadata?: Record<string, unknown>;
}

export interface MemoryMatch {
  text: string;
  type: MemoryType;
  metadata: Record<string, unknown>;
  score: number;
  createdAt: string;
}

const EMBEDDING_DIM = 384; // sentence-transformers/all-MiniLM-L6-v2 via the free HuggingFace Inference API.
const EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2";

let collectionEnsured = false;

function getClient(): QdrantClient {
  return new QdrantClient({ url: config.qdrantUrl, apiKey: config.qdrantApiKey });
}

async function ensureCollection(client: QdrantClient): Promise<void> {
  if (collectionEnsured) return;
  const existing = await client.getCollections();
  const exists = existing.collections.some((c) => c.name === config.memoryCollection);
  if (!exists) {
    await client.createCollection(config.memoryCollection, {
      vectors: { size: EMBEDDING_DIM, distance: "Cosine" },
    });
  }
  collectionEnsured = true;
}

async function embedText(text: string): Promise<number[]> {
  if (!config.huggingfaceApiKey) {
    throw new Error(
      "HUGGINGFACE_API_KEY is not set — required to embed text for Mastra's memory. " +
        "Get a free token at https://huggingface.co/settings/tokens and set it in mastra/.env, " +
        "or skip memory calls in the workflow."
    );
  }
  const response = await fetch(
    `https://router.huggingface.co/hf-inference/models/${EMBEDDING_MODEL}/pipeline/feature-extraction`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${config.huggingfaceApiKey}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ inputs: text, options: { wait_for_model: true } }),
    }
  );
  if (!response.ok) {
    throw new Error(`HuggingFace embedding request failed: ${response.status} ${await response.text()}`);
  }
  const data = (await response.json()) as number[] | number[][];

  // feature-extraction returns either a flat vector (already pooled) or a
  // token-level matrix, depending on the model — mean-pool if it's a matrix.
  if (Array.isArray(data[0])) {
   const matrix = data as number[][];

if (matrix.length === 0 || !matrix[0]) {
  throw new Error("HuggingFace returned an empty embedding.");
}

const dim = matrix[0].length;
const summed = new Array(dim).fill(0);

for (const tokenVec of matrix) {
  for (let i = 0; i < dim; i++) {
    summed[i] += tokenVec[i] ?? 0;
  }
}

return summed.map((v) => v / matrix.length);
  }
  return data as number[];
}

function toPointId(recruiterId: string, type: MemoryType, text: string): string {
  // Deterministic UUID-shaped id derived from a hash — Qdrant requires
  // unsigned int or UUID point ids, same constraint as the Python backend's
  // VectorStore._coerce_point_id, and the same fix: coerce rather than
  // assume the caller already has a valid one.
  const hash = simpleHash(`${recruiterId}:${type}:${text}`);
  return [
    hash.slice(0, 8),
    hash.slice(8, 12),
    "4" + hash.slice(13, 16),
    "8" + hash.slice(17, 20),
    hash.slice(20, 32).padEnd(12, "0"),
  ].join("-");
}

function simpleHash(input: string): string {
  // Not cryptographic — just needs to be deterministic and hex-shaped for a UUID.
  let h1 = 0xdeadbeef;
  let h2 = 0x41c6ce57;
  for (let i = 0; i < input.length; i++) {
    const ch = input.charCodeAt(i);
    h1 = Math.imul(h1 ^ ch, 2654435761);
    h2 = Math.imul(h2 ^ ch, 1597334677);
  }
  h1 = (Math.imul(h1 ^ (h1 >>> 16), 2246822507) ^ Math.imul(h2 ^ (h2 >>> 13), 3266489909)) >>> 0;
  h2 = (Math.imul(h2 ^ (h2 >>> 16), 2246822507) ^ Math.imul(h1 ^ (h1 >>> 13), 3266489909)) >>> 0;
  return (h1.toString(16).padStart(8, "0") + h2.toString(16).padStart(8, "0")).padEnd(32, "0").slice(0, 32);
}

/** Save a memory (a search, a candidate interaction, or a stated preference) for a recruiter. */
export async function remember(record: MemoryRecord): Promise<void> {
  const client = getClient();
  await ensureCollection(client);
  const vector = await embedText(record.text);

  await client.upsert(config.memoryCollection, {
    points: [
      {
        id: toPointId(record.recruiterId, record.type, record.text),
        vector,
        payload: {
          recruiter_id: record.recruiterId,
          type: record.type,
          text: record.text,
          metadata: record.metadata ?? {},
          created_at: new Date().toISOString(),
        },
      },
    ],
  });
}

/** Recall memories for a recruiter, semantically similar to `queryText`, optionally filtered by type. */
export async function recall(params: {
  recruiterId: string;
  queryText: string;
  type?: MemoryType;
  limit?: number;
}): Promise<MemoryMatch[]> {
  const client = getClient();
  await ensureCollection(client);
  const vector = await embedText(params.queryText);

  const mustFilters: Array<Record<string, unknown>> = [{ key: "recruiter_id", match: { value: params.recruiterId } }];
  if (params.type) {
    mustFilters.push({ key: "type", match: { value: params.type } });
  }

  const results = await client.search(config.memoryCollection, {
    vector,
    limit: params.limit ?? 5,
    filter: { must: mustFilters },
  });

  return results.map((r) => {
    const payload = (r.payload ?? {}) as {
      text?: string;
      type?: MemoryType;
      metadata?: Record<string, unknown>;
      created_at?: string;
    };
    return {
      text: payload.text ?? "",
      type: (payload.type ?? "search") as MemoryType,
      metadata: payload.metadata ?? {},
      score: r.score,
      createdAt: payload.created_at ?? "",
    };
  });
}

/** Convenience wrapper: remember a recruiter's job search. */
export function rememberSearch(recruiterId: string, jobTitle: string, jobSkills: string[]): Promise<void> {
  return remember({
    recruiterId,
    type: "search",
    text: `Searched for: ${jobTitle}. Skills: ${jobSkills.join(", ")}`,
    metadata: { jobTitle, jobSkills },
  });
}

/** Convenience wrapper: remember a recruiter's stated hiring preference. */
export function rememberPreference(recruiterId: string, preferenceText: string): Promise<void> {
  return remember({ recruiterId, type: "preference", text: preferenceText });
}