import type { LLMProfile } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";

export async function listLlmProfiles(): Promise<LLMProfile[]> {
  const response = await fetch(`${API_BASE}/admin/llm-profiles`);
  if (!response.ok) throw new Error(`Unable to load profiles (${response.status})`);
  return response.json() as Promise<LLMProfile[]>;
}
