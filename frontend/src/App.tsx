import { useEffect, useState } from "react";
import { listLlmProfiles } from "./api";
import type { LLMProfile } from "./types";

export function App() {
  const [profiles, setProfiles] = useState<LLMProfile[]>([]);
  const [error, setError] = useState<string>();

  useEffect(() => { listLlmProfiles().then(setProfiles).catch((cause: unknown) => setError(cause instanceof Error ? cause.message : "Unknown error")); }, []);
  return <main>
    <h1>航空维修放行人员 AI 口试系统</h1>
    <p>Sprint 1A 管理基础：LLM Profile（考试工作台将在后续 Sprint 实现）。</p>
    {error && <p role="alert">{error}</p>}
    <table><thead><tr><th>Provider</th><th>Model</th><th>资格</th><th>默认</th><th>启用</th></tr></thead>
      <tbody>{profiles.map((profile) => <tr key={profile.id}><td>{profile.provider}</td><td>{profile.model}</td><td>{profile.qualification_status}</td><td>{profile.is_default ? "是" : "否"}</td><td>{profile.enabled ? "是" : "否"}</td></tr>)}</tbody>
    </table>
  </main>;
}
