// Intake form model (wireframes 01a, 01b, 02) and its mapping to the backend profile contract.
// Rule from HANDOFF 2.4: unknown is never false. Unanswered or "not sure" answers are left out
// of the profile entirely instead of being sent as false.

export type Option<T extends string> = { value: T; label: string; short?: string };

// The wireframe used a café as its example; the options cover the MVP persona too
// (HANDOFF 1: home and online product or service businesses, e.g. Maya's candle shop).
export const BUSINESS_TYPE_GROUPS = [
  {
    label: "Products",
    options: [
      { value: "handmade", label: "Handmade or crafted goods", short: "Handmade goods" },
      { value: "online_store", label: "Online store or reselling", short: "Online store" },
    ],
  },
  {
    label: "Services",
    options: [
      { value: "creative", label: "Design, photography or creative work", short: "Creative services" },
      { value: "tutoring", label: "Tutoring, coaching or lessons", short: "Tutoring or lessons" },
      { value: "services_other", label: "Other services", short: "Services" },
    ],
  },
  {
    label: "Food and drink",
    options: [
      { value: "cafe", label: "Café or coffee shop", short: "Café" },
      { value: "restaurant", label: "Restaurant", short: "Restaurant" },
      { value: "bakery", label: "Bakery", short: "Bakery" },
      { value: "food_truck", label: "Food truck", short: "Food truck" },
    ],
  },
  { label: "Other", options: [{ value: "other", label: "Something else", short: "Other" }] },
] as const;
type BusinessTypeOption = (typeof BUSINESS_TYPE_GROUPS)[number]["options"][number];
export const BUSINESS_TYPES: readonly BusinessTypeOption[] = BUSINESS_TYPE_GROUPS.flatMap(
  (g): readonly BusinessTypeOption[] => g.options,
);
export type BusinessType = (typeof BUSINESS_TYPES)[number]["value"];

export const STRUCTURES = [
  { value: "sole_prop", label: "Sole proprietorship", short: "Sole proprietor" },
  { value: "partnership", label: "Partnership", short: "Partnership" },
  { value: "corporation", label: "Corporation", short: "Corporation" },
  { value: "not_sure", label: "Not sure", short: "Not sure" },
] as const satisfies readonly Option<string>[];
export type Structure = (typeof STRUCTURES)[number]["value"];

export const WORKPLACES = [
  { value: "home", label: "From home", short: "From home" },
  { value: "premises", label: "A shop, studio or office", short: "A shop, studio or office" },
  { value: "none", label: "No fixed place", short: "No fixed place" },
] as const satisfies readonly Option<string>[];
export type Workplace = (typeof WORKPLACES)[number]["value"];

export const OPEN_STATUSES = [
  { value: "open", label: "Already open" },
  { value: "soon", label: "Opening soon" },
] as const satisfies readonly Option<string>[];
export type OpenStatus = (typeof OPEN_STATUSES)[number]["value"];

export const ACTIVITIES = [
  { value: "sell_products", label: "Make or sell products" },
  { value: "provide_services", label: "Provide services to clients" },
  { value: "teach", label: "Teach classes or workshops" },
  { value: "markets", label: "Sell at markets, fairs or pop-ups" },
  { value: "serve_on_site", label: "Serve food or drinks on site" },
  { value: "prepare_on_site", label: "Prepare food on site" },
  { value: "takeout", label: "Takeout" },
  { value: "alcohol", label: "Sell or serve alcohol" },
  { value: "outdoor_seating", label: "Outdoor or sidewalk seating" },
  { value: "catering", label: "Catering off site" },
] as const satisfies readonly Option<string>[];
export type Activity = (typeof ACTIVITIES)[number]["value"];

const GOODS_ACTIVITIES: readonly Activity[] = ["sell_products", "serve_on_site", "prepare_on_site", "takeout", "alcohol", "catering"];
const SERVICE_ACTIVITIES: readonly Activity[] = ["provide_services", "teach"];
/** Food safety and liquor permits are out of scope for the MVP (HANDOFF 10.2). */
export const OUT_OF_SCOPE_ACTIVITIES: readonly Activity[] = ["serve_on_site", "prepare_on_site", "takeout", "alcohol", "outdoor_seating", "catering"];

export const STAFF = [
  { value: "just_me", label: "No, just me", short: "Owner only, no employees" },
  { value: "employees", label: "Yes, employees", short: "Has employees" },
  { value: "planning", label: "Not yet, but planning to hire", short: "Planning to hire" },
  { value: "contractors", label: "Contractors only", short: "Contractors only, no employees" },
  { value: "not_sure", label: "Not sure", short: "Not sure" },
] as const satisfies readonly Option<string>[];
export type Staff = (typeof STAFF)[number]["value"];

export const ONLINE = [
  { value: "no", label: "No", short: "No online sales" },
  { value: "website", label: "My own website", short: "Through my own website" },
  { value: "marketplace", label: "Marketplaces like Etsy or Amazon", short: "Through online marketplaces" },
  { value: "apps", label: "Delivery or ordering apps", short: "Through delivery or ordering apps" },
] as const satisfies readonly Option<string>[];
export type Online = (typeof ONLINE)[number]["value"];

export const EXPECTED_SALES = [
  { value: "not_sure", label: "Not sure yet" },
  { value: "under_10k", label: "Under $10,000" },
  { value: "10k_30k", label: "$10,000 to $30,000" },
  { value: "30k_plus", label: "$30,000 or more" },
] as const satisfies readonly Option<string>[];
export type ExpectedSales = (typeof EXPECTED_SALES)[number]["value"];

export const QUICK_ANSWERS = [
  { value: "yes", label: "Yes" },
  { value: "no", label: "No" },
  { value: "not_sure", label: "Not sure" },
] as const satisfies readonly Option<string>[];
/** `skipped` is distinct from unanswered only so the UI can acknowledge the skip. */
export type QuickAnswer = (typeof QUICK_ANSWERS)[number]["value"] | "skipped";

export type IntakeAnswers = {
  businessName: string;
  businessType: BusinessType | null;
  structure: Structure | null;
  address: string;
  workplace: Workplace | null;
  openStatus: OpenStatus | null;
  /** YYYY-MM, only meaningful when openStatus is "soon". */
  openingMonth: string;
  activities: Activity[];
  staff: Staff | null;
  /** YYYY-MM, only meaningful when staff is "planning". */
  plannedHireMonth: string;
  online: Online | null;
  expectedSales: ExpectedSales;
  website: string;
  tradesUnderOtherName: QuickAnswer | null;
  expects30k: QuickAnswer | null;
};

export const EMPTY_ANSWERS: IntakeAnswers = {
  businessName: "",
  businessType: null,
  structure: null,
  address: "",
  workplace: null,
  openStatus: null,
  openingMonth: "",
  activities: [],
  staff: null,
  plannedHireMonth: "",
  online: null,
  expectedSales: "not_sure",
  website: "",
  tradesUnderOtherName: null,
  expects30k: null,
};

export function labelOf<T extends string>(options: readonly Option<T>[], value: T | null): string | undefined {
  return options.find((o) => o.value === value)?.label;
}

export function shortOf<T extends string>(options: readonly Option<T>[], value: T | null): string | undefined {
  const o = options.find((o) => o.value === value);
  return o?.short ?? o?.label;
}

/** The next `count` calendar months starting with the current one, as YYYY-MM with a label. */
export function upcomingMonths(count = 18, from = new Date()): Option<string>[] {
  const months: Option<string>[] = [];
  for (let i = 0; i < count; i++) {
    const d = new Date(from.getFullYear(), from.getMonth() + i, 1);
    const value = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
    months.push({ value, label: formatMonth(value) });
  }
  return months;
}

export function formatMonth(yyyyMm: string): string {
  const [y, m] = yyyyMm.split("-").map(Number);
  return new Date(y, m - 1, 1).toLocaleDateString("en-CA", { month: "long", year: "numeric" });
}

export function openingText(a: IntakeAnswers): string | undefined {
  if (a.openStatus === "open") return "Already open";
  if (a.openStatus === "soon") return a.openingMonth ? formatMonth(a.openingMonth) : "Opening soon";
  return undefined;
}

/** Already-open businesses report the past 12 months; the rest estimate their first 12. */
export function salesLabel(a: IntakeAnswers): string {
  return a.openStatus === "open" ? "Sales in the past 12 months" : "Expected sales in your first 12 months";
}

/** Sales band after the step 3 GST question, which only asks when step 2 said "Not sure yet". */
export function salesText(a: IntakeAnswers): string | undefined {
  if (a.expectedSales !== "not_sure") return labelOf(EXPECTED_SALES, a.expectedSales);
  if (a.expects30k === "yes") return "$30,000 or more";
  if (a.expects30k === "no") return "Under $30,000";
  return undefined;
}

export function staffText(a: IntakeAnswers): string | undefined {
  if (a.staff === "planning" && a.plannedHireMonth) return `Planning to hire in ${formatMonth(a.plannedHireMonth)}`;
  return shortOf(STAFF, a.staff);
}

export type FactRow = { label: string; value: string | undefined; step: 1 | 2 };

/** Rows for step 3. A row with no value is shown as not answered. */
export function factRows(a: IntakeAnswers): FactRow[] {
  const activities = a.activities.map((v) => labelOf(ACTIVITIES, v)).filter(Boolean);
  return [
    { step: 1, label: "Business name", value: a.businessName.trim() || undefined },
    { step: 1, label: "Type of business", value: labelOf(BUSINESS_TYPES, a.businessType) },
    { step: 1, label: "Structure", value: shortOf(STRUCTURES, a.structure) },
    {
      step: 1,
      label: "Location",
      value: a.address.trim() ? `${a.address.trim()}, Vancouver, BC` : "Vancouver, BC",
    },
    { step: 1, label: "Where you run it", value: shortOf(WORKPLACES, a.workplace) },
    { step: 1, label: "Opening", value: openingText(a) },
    { step: 2, label: "Activities", value: activities.length ? activities.join(", ") : undefined },
    { step: 2, label: "People working in the business", value: staffText(a) },
    { step: 2, label: "Online sales", value: shortOf(ONLINE, a.online) },
    { step: 2, label: salesLabel(a), value: salesText(a) },
    ...(a.website.trim() ? [{ step: 2 as const, label: "Website", value: a.website.trim() }] : []),
  ];
}

/** Step 3 questions, shown only while the answer is still unknown from earlier steps. */
export function quickQuestions(a: IntakeAnswers) {
  return [
    {
      key: "tradesUnderOtherName" as const,
      question: "Will you trade under a name other than your own legal name?",
      affects: "Business name registration",
    },
    ...(a.expectedSales === "not_sure"
      ? [
          {
            key: "expects30k" as const,
            question:
              a.openStatus === "open"
                ? "Have you made $30,000 or more in sales in the past 12 months?"
                : "Do you expect $30,000 or more in sales in your first 12 months?",
            affects: "GST/HST registration",
          },
        ]
      : []),
  ];
}

// Backend contract: POST /profile (backend/app/intake/profile_service.py ProfileCreate).
export type FactValue = { value: unknown; confirmed: boolean };
export type ProfileCreate = {
  trading_name: string | null;
  facts: Record<string, FactValue>;
};

/**
 * Maps answers onto fact-dictionary keys (backend/app/intake/fact_dictionary.py). Everything the
 * owner entered here is confirmed by submitting step 3. Answers with no matching fact key
 * (business type, address, opening, sales band) are not sent. Unchecked activities never set a
 * fact to false; `sells` comes only from what was checked.
 */
export function toProfileCreate(a: IntakeAnswers): ProfileCreate {
  const facts: Record<string, FactValue> = {};
  const set = (key: string, value: unknown) => (facts[key] = { value, confirmed: true });

  const did = (list: readonly Activity[]) => a.activities.some((v) => list.includes(v));

  set("operates_in_vancouver", true);

  if (a.workplace === "home") set("home_based", true);
  if (a.workplace === "premises") {
    set("home_based", false);
    set("has_established_premises", true);
  }
  if (a.workplace === "none") set("home_based", false);

  const goods = did(GOODS_ACTIVITIES);
  const services = did(SERVICE_ACTIVITIES);
  if (goods || services) set("sells", goods && services ? "both" : goods ? "goods" : "services");
  if (a.activities.includes("markets")) set("sells_at_recurring_markets", true);

  if (a.staff === "employees") set("has_employees", true);
  if (a.staff === "just_me" || a.staff === "contractors" || a.staff === "planning") set("has_employees", false);
  if (a.staff === "planning") {
    set("plans_to_hire", true);
    if (a.plannedHireMonth) set("planned_hire_date", a.plannedHireMonth);
  }

  // Market or premises sales are in person, so the business is not online-only.
  if (a.online === "no" || a.activities.includes("markets") || a.workplace === "premises") set("online_only", false);
  if (a.tradesUnderOtherName === "yes") set("trading_name_differs_from_legal_name", true);
  if (a.tradesUnderOtherName === "no") set("trading_name_differs_from_legal_name", false);

  return { trading_name: a.businessName.trim() || null, facts };
}
