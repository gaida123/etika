// Calls go to /api/*, which next.config.ts rewrites to the FastAPI backend.
// Types mirror backend/app/contracts and the route response models.

import type { ProfileCreate } from "./intake";

export type Area = "registration" | "tax" | "employer";
export type Priority = "high" | "medium" | "low";
export type Applicability = "required_now" | "upcoming" | "not_applicable" | "undetermined";
export type FindingStatus = "done" | "in_progress" | "not_done" | "not_yet_required" | "undetermined";

export type FactValue = { value: unknown; confirmed: boolean };

export type BusinessProfile = {
  business_id: string;
  profile_version: number;
  legal_name: string | null;
  trading_name: string | null;
  facts: Record<string, FactValue>;
  monthly_revenue: { month: string; amount: string | number }[];
};

export type SourceLink = { title: string; url: string };

export type AssessmentItem = {
  requirement_id: string;
  title: string;
  area: Area;
  priority: Priority;
  applicability: Applicability;
  status: FindingStatus | null;
  explanation: string | null;
  action_url: string | null;
  sources: SourceLink[];
  progress: { current: number; threshold: number; estimated_crossing?: string | null; outcome?: string } | null;
  trigger: string | null;
  missing_facts: string[];
};

export type Claim = { text: string; chunk_ids: string[] };

export type Finding = {
  requirement_id: string;
  status: FindingStatus;
  explanation: string;
  claims: Claim[];
  flags: string[];
  confidence: number;
};

export type Assessment = {
  assessment_id: string;
  business_id: string;
  profile_version: number;
  score: number | null;
  area_scores: Record<Area, number | null>;
  now: AssessmentItem[];
  next: AssessmentItem[];
  later: AssessmentItem[];
  flags: { requirement_id: string; reason: string }[];
  findings: Finding[];
  agents: { agent: Area; mode: string | null; tool_calls: number; findings: number; error: string | null }[];
  cached: boolean;
  cached_at: string | null;
  disclaimer: string;
};

export type FollowUpQuestion = {
  fact_key: string;
  question: string;
  answer_type: "bool" | "enum" | "month" | "text" | "monthly_revenue";
  options: string[];
  needed_for: string[];
};

export type RetrievedChunk = {
  chunk_id: string;
  source_id: string;
  text: string;
  title: string;
  section_path: string | null;
  url: string;
  source_version: string;
};

export type RequirementDetail = {
  requirement: {
    id: string;
    area: Area;
    title: string;
    requirement_type: "legal_obligation" | "recommendation";
    timing: "now" | "trigger" | "recommendation";
    required_fact_keys: string[];
    depends_on: string[];
    priority: Priority;
    action_url: string;
    preparation_items: string[];
    review_flags: string[];
    last_verified_at: string | null;
  };
  evidence: { status: "supported" | "insufficient_evidence"; chunks: RetrievedChunk[]; limitations: string[] };
};

export type ProposedFact = { key: string; value: unknown; confidence: number; evidence: string };

export type ChatResponse = {
  conversation_id: string;
  agent: Area;
  answer: string;
  insufficient_evidence: boolean;
  claims: Claim[];
  sources: SourceLink[];
  proposal_id: string | null;
  proposed_facts: ProposedFact[];
  disclaimer: string;
};

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status?: number,
  ) {
    super(message);
  }
}

const UNREACHABLE = "Couldn't reach the server. Check that the backend is running.";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`/api${path}`, {
      ...init,
      headers: init?.body ? { "Content-Type": "application/json" } : undefined,
    });
  } catch {
    throw new ApiError(UNREACHABLE);
  }
  if (!res.ok) {
    const detail = await res.json().then((j) => j?.detail, () => undefined);
    if (res.status >= 500 && typeof detail !== "string") throw new ApiError(UNREACHABLE, res.status);
    throw new ApiError(typeof detail === "string" ? detail : `Request failed (${res.status}).`, res.status);
  }
  return res.json();
}

const post = (body?: unknown): RequestInit => ({
  method: "POST",
  body: body === undefined ? undefined : JSON.stringify(body),
});

export const createProfile = (body: ProfileCreate) => request<BusinessProfile>("/profile", post(body));

export const getProfile = (businessId: string) => request<BusinessProfile>(`/profile/${businessId}`);

export const runAssessment = (businessId: string) => request<Assessment>(`/assess/${businessId}`, post());

export const getQuestions = (businessId: string) =>
  request<FollowUpQuestion[]>(`/profile/${businessId}/questions`);

export const getRequirement = (id: string) => request<RequirementDetail>(`/requirements/${id}`);

export type FactAnswers = {
  facts?: Record<string, unknown>;
  monthly_revenue?: { month: string; amount: number }[];
};

export const askChat = (businessId: string, question: string) =>
  request<ChatResponse>("/chat", post({ business_id: businessId, question }));

export const confirmProposal = (
  businessId: string,
  proposalId: string,
  accepted: string[],
  edits: Record<string, unknown> = {},
) =>
  request<{ applied_keys: string[]; profile: BusinessProfile }>(
    `/profile/${businessId}/confirm-update`,
    post({ proposal_id: proposalId, accepted, edits }),
  );
