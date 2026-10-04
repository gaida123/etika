"use client";

// Loads one business's profile and assessment for every page under /b/[id] and holds the chat
// conversation, so moving between the dashboard, a requirement and Ask etika doesn't re-run agents.

import { createContext, type ReactNode, use, useCallback, useEffect, useMemo, useState } from "react";
import {
  ApiError,
  type Assessment,
  type AgentTraceEntry,
  type BusinessProfile,
  type ChatResponse,
  type FactAnswers,
  type FollowUpQuestion,
} from "@/lib/api";
import { type Backend, backendFor } from "@/lib/backend";
import { DEMO_ID } from "@/lib/demo";
import { type Marks, type Progress, type Row, rowsOf } from "@/lib/assessment";
import { useStored } from "@/lib/stored";

export type ChatTurn = {
  id: string;
  question: string;
  /** Requirement the question was asked about, if any. */
  topic: string | null;
  response?: ChatResponse;
  error?: string;
  proposal?: "open" | "saving" | "confirmed" | "dismissed";
  proposalError?: string;
};

type Ctx = {
  businessId: string;
  backend: Backend;
  /** Sample data at /b/demo; nothing is sent to the backend. */
  isDemo: boolean;
  profile: BusinessProfile | null;
  assessment: Assessment | null;
  trace: AgentTraceEntry[];
  rows: Row[];
  questions: FollowUpQuestion[];
  phase: "loading" | "assessing" | "ready" | "error";
  error: string | null;
  /** True while a re-check runs on top of results that are still shown. */
  rechecking: boolean;
  marks: Marks;
  setMark: (requirementId: string, progress: Progress) => void;
  retry: () => void;
  answer: (answers: FactAnswers) => Promise<void>;
  turns: ChatTurn[];
  ask: (question: string, topic: string | null) => void;
  confirmTurn: (turnId: string, edits: Record<string, unknown>) => Promise<void>;
  dismissTurn: (turnId: string) => void;
};

const BusinessContext = createContext<Ctx | null>(null);

export function useBusiness(): Ctx {
  const ctx = use(BusinessContext);
  if (!ctx) throw new Error("useBusiness must be used inside BusinessProvider");
  return ctx;
}

type Cached = {
  version: number;
  assessment: Assessment;
  questions: FollowUpQuestion[];
  /** Optional so existing browser caches stay valid after trace support ships. */
  trace?: AgentTraceEntry[];
};
const cacheKey = (id: string) => `etika:assessment:${id}`;

function readCache(id: string): Cached | null {
  if (id === DEMO_ID) return null;
  try {
    const raw = window.sessionStorage.getItem(cacheKey(id));
    return raw ? (JSON.parse(raw) as Cached) : null;
  } catch {
    return null;
  }
}

function writeCache(id: string, value: Cached) {
  if (id === DEMO_ID) return;
  try {
    window.sessionStorage.setItem(cacheKey(id), JSON.stringify(value));
  } catch {
    // Without storage a reload re-runs the check; nothing else depends on it.
  }
}

const message = (e: unknown) => (e instanceof ApiError ? e.message : "Something went wrong. Try again.");

export function BusinessProvider({ businessId, children }: { businessId: string; children: ReactNode }) {
  const [profile, setProfile] = useState<BusinessProfile | null>(null);
  const [assessment, setAssessment] = useState<Assessment | null>(null);
  const [trace, setTrace] = useState<AgentTraceEntry[]>([]);
  const [questions, setQuestions] = useState<FollowUpQuestion[]>([]);
  const [phase, setPhase] = useState<Ctx["phase"]>("loading");
  const [error, setError] = useState<string | null>(null);
  const [rechecking, setRechecking] = useState(false);
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [attempt, setAttempt] = useState(0);
  const [marks, setMarks] = useStored<Marks>(`etika:marks:${businessId}`, {});
  const backend = useMemo(() => backendFor(businessId), [businessId]);

  const assess = useCallback(
    async (p: BusinessProfile) => {
      const assessmentPromise = backend.runAssessment(businessId);
      const questionsPromise = backend.getQuestions(businessId);
      const a = await assessmentPromise;
      // A trace makes the agent work inspectable, but it must never hide an otherwise usable assessment.
      const [q, nextTrace] = await Promise.all([questionsPromise, backend.getAssessmentTrace(a.assessment_id).catch(() => [])]);
      setAssessment(a);
      setTrace(nextTrace);
      setQuestions(q);
      writeCache(businessId, { version: p.profile_version, assessment: a, questions: q, trace: nextTrace });
    },
    [backend, businessId],
  );

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const p = await backend.getProfile(businessId);
        if (cancelled) return;
        setProfile(p);
        const cached = readCache(businessId);
        if (cached?.version === p.profile_version) {
          setAssessment(cached.assessment);
          setQuestions(cached.questions);
          setTrace(cached.trace ?? []);
          if (!cached.trace) {
            backend.getAssessmentTrace(cached.assessment.assessment_id).then(
              (cachedTrace) => !cancelled && setTrace(cachedTrace),
              () => undefined,
            );
          }
        } else {
          setPhase("assessing");
          await assess(p);
        }
        if (!cancelled) setPhase("ready");
      } catch (e) {
        if (cancelled) return;
        setError(e instanceof ApiError && e.status === 404 ? "We couldn't find this business." : message(e));
        setPhase("error");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [backend, businessId, assess, attempt]);

  const recheck = useCallback(
    async (p: BusinessProfile) => {
      setProfile(p);
      setRechecking(true);
      try {
        await assess(p);
      } finally {
        setRechecking(false);
      }
    },
    [assess],
  );

  const answer = useCallback(
    async (answers: FactAnswers) => recheck(await backend.answerFacts(businessId, answers)),
    [backend, businessId, recheck],
  );

  const rows = useMemo(() => (assessment ? rowsOf(assessment) : []), [assessment]);

  const updateTurn = (id: string, patch: Partial<ChatTurn>) =>
    setTurns((ts) => ts.map((t) => (t.id === id ? { ...t, ...patch } : t)));

  const ask = useCallback(
    (question: string, topic: string | null) => {
      const id = crypto.randomUUID();
      setTurns((ts) => [...ts, { id, question, topic }]);
      const title = topic ? rows.find((r) => r.requirement_id === topic)?.title : undefined;
      backend.askChat(businessId, title ? `About "${title}": ${question}` : question).then(
        (response) =>
          updateTurn(id, {
            response,
            proposal: response.proposal_id && response.proposed_facts.length ? "open" : undefined,
          }),
        (e) => updateTurn(id, { error: message(e) }),
      );
    },
    [backend, businessId, rows],
  );

  const confirmTurn = useCallback(
    async (turnId: string, edits: Record<string, unknown>) => {
      const turn = turns.find((t) => t.id === turnId);
      const r = turn?.response;
      if (!r?.proposal_id) return;
      updateTurn(turnId, { proposal: "saving", proposalError: undefined });
      try {
        const res = await backend.confirmProposal(businessId, r.proposal_id, r.proposed_facts.map((f) => f.key), edits);
        await recheck(res.profile);
        updateTurn(turnId, { proposal: "confirmed" });
      } catch (e) {
        updateTurn(turnId, { proposal: "open", proposalError: message(e) });
      }
    },
    [backend, businessId, recheck, turns],
  );

  const value: Ctx = {
    businessId,
    backend,
    isDemo: businessId === DEMO_ID,
    profile,
    assessment,
    trace,
    rows,
    questions,
    phase,
    error,
    rechecking,
    marks,
    setMark: (id, progress) => setMarks({ ...marks, [id]: progress }),
    retry: () => {
      setError(null);
      setPhase("loading");
      setAttempt((n) => n + 1);
    },
    answer,
    turns,
    ask,
    confirmTurn,
    dismissTurn: (id) => updateTurn(id, { proposal: "dismissed" }),
  };

  return <BusinessContext value={value}>{children}</BusinessContext>;
}
