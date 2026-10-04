// Plain-English labels for fact-dictionary keys (backend/app/intake/fact_dictionary.py).

const MONTH_FMT: Intl.DateTimeFormatOptions = { month: "long", year: "numeric" };

function month(v: unknown): string {
  const [y, m] = String(v).split("-").map(Number);
  return y && m ? new Date(y, m - 1, 1).toLocaleDateString("en-CA", MONTH_FMT) : String(v);
}

type Spec = { field: string; yes?: string; no?: string; format?: (v: unknown) => string };

const SPECS: Record<string, Spec> = {
  legal_name: { field: "Legal name" },
  trading_name: { field: "Business name" },
  trading_name_differs_from_legal_name: {
    field: "Trading name",
    yes: "Trades under a name other than your legal name",
    no: "Trades under your own legal name",
  },
  operates_in_vancouver: { field: "Location", yes: "Located in City of Vancouver", no: "Outside City of Vancouver" },
  home_based: { field: "Where you work", yes: "Runs from home", no: "Not run from home" },
  online_only: { field: "Online sales", yes: "Sells only online", no: "Sells in person too" },
  sells: {
    field: "What you sell",
    format: (v) => ({ goods: "Sells goods", services: "Sells services", both: "Sells goods and services" })[String(v)] ?? String(v),
  },
  has_established_premises: {
    field: "Business premises",
    yes: "Has a shop, studio or office",
    no: "No separate business premises",
  },
  sells_at_recurring_markets: {
    field: "Markets and pop-ups",
    yes: "Sells regularly at markets",
    no: "Doesn't sell at markets",
  },
  has_employees: { field: "People working in the business", yes: "Has employees", no: "Owner only, no employees" },
  plans_to_hire: { field: "Hiring plans", yes: "Planning to hire", no: "Not planning to hire" },
  planned_hire_date: { field: "Planned hire date", format: (v) => `Hiring in ${month(v)}` },
  monthly_revenue: { field: "Monthly sales", format: (v) => `${v} months of sales entered` },
};

export const factField = (key: string) => SPECS[key]?.field ?? key.replaceAll("_", " ");

/** A fact as a short statement, e.g. "Runs from home". */
export function factText(key: string, value: unknown): string {
  const s = SPECS[key];
  if (value === null || value === undefined) return "Unknown";
  if (s?.format) return s.format(value);
  if (typeof value === "boolean") return (value ? s?.yes : s?.no) ?? `${factField(key)}: ${value ? "yes" : "no"}`;
  return String(value);
}
