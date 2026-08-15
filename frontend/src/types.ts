export type QualificationStatus = "UNTESTED" | "QUALIFYING" | "QUALIFIED" | "CONDITIONAL" | "FAILED" | "RETIRED";

export interface LLMProfile {
  id: string;
  provider: string;
  model: string;
  display_name: string;
  enabled: boolean;
  is_default: boolean;
  qualification_status: QualificationStatus;
  qualification_summary: Record<string, unknown>;
}
