// Sample data for previewing every screen without the backend: open /b/demo.
//
// Maya's "Wick & Co" from HANDOFF 3.2. Requirement titles, priorities, fact keys, prep items and gray
// areas match backend/data/registry/requirements.json. Explanations follow the business rules in
// HANDOFF 2. Source passages are labelled samples, not official text, and links are left empty.
// State lives in memory, so a reload resets the preview.

import type {
  Assessment,
  AssessmentItem,
  BusinessProfile,
  ChatResponse,
  FactAnswers,
  FollowUpQuestion,
  RequirementDetail,
} from "./api";

export const DEMO_ID = "demo";

const NO_LINK = "sample-link";

type Spec = Omit<RequirementDetail["requirement"], "requirement_type" | "timing" | "action_url" | "last_verified_at"> & {
  recommendation?: boolean;
  source: string;
  passage: string;
  explanation: string;
};

const SPECS: Spec[] = [
  {
    id: "REG-01", area: "registration", title: "Register your business name with BC Registries", priority: "high",
    required_fact_keys: ["trading_name_differs_from_legal_name"], depends_on: [],
    preparation_items: ["Choose the trading name", "Submit a name approval request"],
    review_flags: ["Using own name with a tagline"],
    source: "BC Registries, proprietorship registration",
    passage: "A sole proprietor who trades under a name other than their own legal name registers that name, after a name approval request.",
    explanation: "You trade as Wick & Co, which isn't your legal name, so BC requires you to register that name. A name approval request comes first.",
  },
  {
    id: "REG-02", area: "registration", title: "Get a City of Vancouver business licence", priority: "high",
    required_fact_keys: ["operates_in_vancouver", "home_based", "online_only"], depends_on: [],
    preparation_items: ["Confirm business address", "Describe business activity"],
    review_flags: ["Home-based and online-only licensing (research owner to verify)"],
    source: "City of Vancouver, business licences",
    passage: "Businesses operating in the City of Vancouver, including home-based businesses, need a business licence.",
    explanation: "You run the business from your home in Vancouver and sell in person at markets, so a city business licence likely applies.",
  },
  {
    id: "REG-03", area: "registration", title: "Get a CRA business number", priority: "high",
    required_fact_keys: [], depends_on: [], preparation_items: ["Legal name and address", "Social insurance number"],
    review_flags: [], source: "CRA, business number",
    passage: "A business number is needed before you can open a GST/HST or payroll account.",
    explanation: "You don't need one yet. It becomes necessary before you register for GST or open a payroll account.",
  },
  {
    id: "TAX-01", area: "tax", title: "Register for BC PST", priority: "high",
    required_fact_keys: ["sells", "monthly_revenue", "has_established_premises"], depends_on: [],
    preparation_items: ["Gather sales records for the past 12 months"],
    review_flags: ["Market stalls and the established premises condition", "Goods vs services split"],
    source: "BC Ministry of Finance, PST small sellers",
    passage: "Small sellers with gross sales of $10,000 or less over the past 12 months and no established business premises don't need to register.",
    explanation: "You've sold about $8,200 over the past 12 months with no business premises, so you're still under the small seller line. At your current pace you'd cross $10,000 around March.",
  },
  {
    id: "TAX-02", area: "tax", title: "Register for GST", priority: "high",
    required_fact_keys: ["monthly_revenue"], depends_on: ["REG-03"], preparation_items: ["Gather quarterly sales totals"],
    review_flags: ["Revenue data missing"], source: "CRA, small suppliers",
    passage: "You must register for GST/HST once your taxable sales pass $30,000 in a single calendar quarter or over four consecutive quarters.",
    explanation: "You're well under the $30,000 small supplier line, so GST registration isn't required yet.",
  },
  {
    id: "TAX-03", area: "tax", title: "Consider voluntary GST registration", priority: "low", recommendation: true,
    required_fact_keys: ["monthly_revenue"], depends_on: ["REG-03"], preparation_items: ["Estimate GST paid on business purchases"],
    review_flags: ["Whether business purchases are significant enough to benefit"], source: "CRA, voluntary registration",
    passage: "Small suppliers can choose to register for GST/HST before they reach the threshold.",
    explanation: "Optional. Registering early lets you claim back GST on business purchases, but you'd also have to charge it.",
  },
  {
    id: "TAX-04", area: "tax", title: "Charge and show the correct tax on invoices once registered", priority: "medium",
    required_fact_keys: ["sells", "monthly_revenue"], depends_on: [],
    preparation_items: ["Update invoice template with tax registration numbers"], review_flags: ["Which items are PST-taxable"],
    source: "BC Ministry of Finance, charging PST",
    passage: "Once registered, you charge tax on taxable sales and show it on your invoices and receipts.",
    explanation: "This switches on once you register for PST or GST.",
  },
  ...(
    [
      ["EMP-01", "Register with WorkSafeBC", "high", ["Estimated payroll for the year", "Description of work performed"], ["Contractor vs employee", "Family members helping out"], "WorkSafeBC, employer registration", "Employers register with WorkSafeBC before their first worker starts."],
      ["EMP-02", "Open a CRA payroll account", "high", ["CRA business number", "First pay date"], ["Contractor vs employee"], "CRA, payroll accounts", "Employers open a payroll account to deduct and remit income tax, CPP and EI."],
      ["EMP-03", "Pay at least the BC minimum wage ($18.25/hour)", "high", ["Set hourly rate at or above minimum wage"], [], "Province of BC, minimum wage", "The general minimum wage in BC is $18.25 an hour as of June 1, 2026."],
      ["EMP-04", "Give a pay statement every payday", "medium", ["Pay statement template"], [], "Employment Standards Act, wage statements", "Employers give each employee a written wage statement every payday."],
      ["EMP-05", "Keep payroll records for the required period", "medium", ["Set up a payroll records folder"], ["Retention period (research owner to verify)"], "Employment Standards Act, records", "Employers keep payroll records for each employee for a set period."],
      ["EMP-06", "Check employee vs contractor status", "low", ["Describe the work, schedule and tools provided"], ["Contractor vs employee", "Family members helping out"], "CRA, employee or self-employed", "Whether someone is an employee or a contractor depends on the working relationship, not the label."],
    ] as const
  ).map(
    ([id, title, priority, prep, flags, source, passage]): Spec => ({
      id, area: "employer", title, priority, recommendation: id === "EMP-06",
      required_fact_keys: ["has_employees", "plans_to_hire"], depends_on: id === "EMP-02" ? ["REG-03"] : [],
      preparation_items: [...prep], review_flags: [...flags], source, passage,
      explanation: "This switches on the day you hire your first employee.",
    }),
  ),
];

const NOW = ["REG-01", "REG-02"];
const NEXT = ["REG-03", "TAX-01", "TAX-02", "TAX-03", "TAX-04"];
const EMPLOYER = ["EMP-01", "EMP-02", "EMP-03", "EMP-04", "EMP-05", "EMP-06"];

function item(id: string, patch: Partial<AssessmentItem> = {}): AssessmentItem {
  const s = SPECS.find((x) => x.id === id)!;
  return {
    requirement_id: id, title: s.title, area: s.area, priority: s.priority,
    applicability: "upcoming", status: "not_yet_required", explanation: s.explanation, action_url: NO_LINK,
    sources: [{ title: s.source, url: NO_LINK }], progress: null, trigger: null, missing_facts: [],
    ...patch,
  };
}

// Mutable preview state.
let hired = false;
let profile: BusinessProfile = {
    business_id: DEMO_ID, profile_version: 1, legal_name: "Maya Chen", trading_name: "Wick & Co",
    facts: Object.fromEntries(
      Object.entries({
        trading_name_differs_from_legal_name: true, operates_in_vancouver: true, home_based: true, online_only: false,
        sells: "goods", has_established_premises: false, sells_at_recurring_markets: true, has_employees: false,
      }).map(([k, value]) => [k, { value, confirmed: true }]),
    ),
    monthly_revenue: [450, 500, 520, 560, 600, 620, 650, 700, 750, 800, 950, 1100].map((amount, i) => ({
      month: `${i < 3 ? 2025 : 2026}-${String(((i + 9) % 12) + 1).padStart(2, "0")}`,
      amount,
    })),
};
let questions: FollowUpQuestion[] = [
  {
    fact_key: "plans_to_hire", question: "Are you planning to hire anyone?", answer_type: "bool", options: [],
    needed_for: EMPLOYER,
  },
];

function assessment(): Assessment {
  const planning = profile.facts.plans_to_hire?.value;
  const employer = EMPLOYER.map((id) =>
    hired && id !== "EMP-06"
      ? item(id, {
          applicability: "required_now", status: "not_done",
          explanation: "You've hired someone, so this applies from their first day.",
        })
      : item(id, { trigger: id === "EMP-06" ? null : "first_hire", missing_facts: planning === undefined && !hired ? ["plans_to_hire"] : [] }),
  );
  // Hiring moves the business number and five employer obligations into Now (HANDOFF 3.2).
  const now = [
    ...NOW.map((id) => item(id, { applicability: "required_now", status: "not_done" })),
    ...(hired
      ? [
          item("REG-03", {
            applicability: "required_now", status: "not_done",
            explanation: "You need a business number before you can open a payroll account.",
          }),
          ...employer.filter((e) => e.applicability === "required_now"),
        ]
      : []),
  ];
  const next = NEXT.filter((id) => !(hired && id === "REG-03")).map((id) =>
    item(id, {
      progress:
        id === "TAX-01"
          ? { current: 8200, threshold: 10000, estimated_crossing: "2027-03" }
          : id === "TAX-02"
            ? { current: 8200, threshold: 30000, estimated_crossing: null }
            : null,
      trigger: id === "TAX-01" ? "pst_small_seller_test" : id.startsWith("TAX-0") && id !== "TAX-04" ? "gst_small_supplier_test" : null,
    }),
  );
  const later = employer.filter((e) => e.applicability !== "required_now");
  return {
    assessment_id: `demo-${profile.profile_version}`, business_id: DEMO_ID, profile_version: profile.profile_version,
    score: 0, area_scores: { registration: 0, tax: null, employer: hired ? 0 : null },
    now, next, later,
    flags: [{ requirement_id: "TAX-01", reason: "Regular market sales may affect the premises condition" }],
    findings: [...now, ...next, ...later].map((i) => ({
      requirement_id: i.requirement_id, status: i.status ?? "undetermined", explanation: i.explanation ?? "",
      claims: [], confidence: 0.8,
      flags: i.requirement_id === "TAX-01" ? ["Regular market sales may affect the premises condition"] : [],
    })),
    agents: (["registration", "tax", "employer"] as const).map((agent) => ({ agent, mode: null, tool_calls: 4, findings: 0, error: null })),
    cached: false, cached_at: null, disclaimer: "General information, not legal advice.",
  };
}

const wait = <T,>(value: T, ms = 500) => new Promise<T>((r) => setTimeout(() => r(structuredClone(value)), ms));

let chatCount = 0;

export const demoBackend = {
  getProfile: () => wait(profile, 150),
  runAssessment: () => wait(assessment(), 1200),
  getQuestions: () => wait(questions, 50),
  getRequirement: (id: string) => {
    const s = SPECS.find((x) => x.id === id);
    if (!s) return Promise.reject(new Error("Requirement not found"));
    const detail: RequirementDetail = {
      requirement: {
        ...s, requirement_type: s.recommendation ? "recommendation" : "legal_obligation",
        timing: NOW.includes(id) ? "now" : s.recommendation ? "recommendation" : "trigger",
        action_url: NO_LINK, last_verified_at: null,
      },
      evidence: {
        status: "supported", limitations: [],
        chunks: [{ chunk_id: `${id}-a`, source_id: id, text: `[Sample passage] ${s.passage}`, title: s.source, section_path: null, url: NO_LINK, source_version: "sample" }],
      },
    };
    return wait(detail, 300);
  },
  answerFacts: (_: string, answers: FactAnswers) => {
    for (const [key, value] of Object.entries(answers.facts ?? {})) profile.facts[key] = { value, confirmed: true };
    questions = questions.filter((q) => !(q.fact_key in (answers.facts ?? {})));
    profile = { ...profile, profile_version: profile.profile_version + 1 };
    return wait(profile, 300);
  },
  askChat: (_: string, question: string): Promise<ChatResponse> => {
    chatCount++;
    const base = { conversation_id: `demo-${chatCount}`, claims: [], disclaimer: "General information, not legal advice.", proposal_id: null, proposed_facts: [] };
    if (/hir|employ|staff|help(er)? for/i.test(question))
      return wait({
        ...base, agent: "employer", insufficient_evidence: false, sources: [],
        answer: "Hiring someone switches on five employer obligations from their first day.",
        proposal_id: "demo-proposal", proposed_facts: [{ key: "has_employees", value: true, confidence: 0.9, evidence: question }],
      }, 900);
    if (/seattle|surrey|alberta|liquor|alcohol|insurance|food/i.test(question))
      return wait({
        ...base, agent: "registration", insufficient_evidence: true, sources: [],
        answer: "We could not find enough support in the available sources to answer this confidently.",
      }, 900);
    const tax = /pst|gst|tax|sell|sales/i.test(question);
    const s = SPECS.find((x) => x.id === (tax ? "TAX-01" : "REG-02"))!;
    return wait({
      ...base, agent: tax ? "tax" : "registration", insufficient_evidence: false, sources: [{ title: s.source, url: NO_LINK }],
      answer: tax
        ? "Not yet. You've sold about $8,200 over the past 12 months and have no business premises, so you're under the $10,000 small seller line. At your current pace you'd cross it around March, and regular market sales could affect the premises condition, so check that."
        : "Most likely yes. Businesses operating in the City of Vancouver, including home-based ones, need a city business licence. Whether online-only sales change that is still being confirmed.",
    }, 900);
  },
  confirmProposal: (_: string, __: string, accepted: string[], edits: Record<string, unknown> = {}) => {
    for (const key of accepted) profile.facts[key] = { value: key in edits ? edits[key] : true, confirmed: true };
    hired = profile.facts.has_employees?.value === true;
    questions = questions.filter((q) => !(hired && q.fact_key === "plans_to_hire"));
    profile = { ...profile, profile_version: profile.profile_version + 1 };
    return wait({ applied_keys: accepted, profile }, 300);
  },
};
