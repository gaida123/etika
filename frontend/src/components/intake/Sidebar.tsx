import { CheckIcon, Logo } from "@/components/ui";
import { BUSINESS_TYPES, type IntakeAnswers, STRUCTURES, openingText, shortOf } from "@/lib/intake";

export const STEPS = ["Business basics", "What you do", "Check our understanding"] as const;
export type Step = 1 | 2 | 3;

export function Sidebar({
  step,
  answers,
  onGoTo,
}: {
  step: Step;
  answers: IntakeAnswers;
  onGoTo: (step: Step) => void;
}) {
  const summary = [
    ["Type", shortOf(BUSINESS_TYPES, answers.businessType)],
    ["Where", answers.workplace === "home" ? "Home, Vancouver, BC" : "Vancouver, BC"],
    ["Structure", shortOf(STRUCTURES, answers.structure)],
    ["Opening", openingText(answers)],
  ].filter((r): r is [string, string] => Boolean(r[1]));

  return (
    <aside className="side" aria-label="Setup">
      <Logo />

      <nav aria-label="Setup steps">
        <div className="navh">Set up your check</div>
        <ol className="m-0 flex list-none flex-col gap-0.5 p-0">
          {STEPS.map((label, i) => {
            const n = (i + 1) as Step;
            if (n === step) {
              return (
                <li key={label}>
                  <span className="nav nav-on" aria-current="step">
                    <StepDot n={n} state="current" />
                    {label}
                  </span>
                </li>
              );
            }
            if (n < step) {
              return (
                <li key={label}>
                  <button type="button" className="nav" onClick={() => onGoTo(n)}>
                    <StepDot n={n} state="done" />
                    {label}
                  </button>
                </li>
              );
            }
            return (
              <li key={label}>
                <span className="nav muted">
                  <StepDot n={n} state="todo" />
                  {label}
                </span>
              </li>
            );
          })}
        </ol>
      </nav>

      {step < 3 && (
        <div className="box flex flex-col gap-1.5 p-3.5">
          <div className="text-[13px] font-medium">Your business so far</div>
          {step === 1 ? (
            <p className="muted m-0 text-[13px]">
              This fills in as you answer. Nothing is checked until you confirm everything on step 3.
            </p>
          ) : (
            <dl className="m-0 grid grid-cols-[auto_1fr] gap-x-2.5 gap-y-1 text-[13px]">
              {summary.map(([k, v]) => (
                <div key={k} className="contents">
                  <dt className="muted">{k}</dt>
                  <dd className="m-0">{v}</dd>
                </div>
              ))}
            </dl>
          )}
        </div>
      )}

      <p className="muted mt-auto mb-0 px-2.5 text-[13px]">
        {step < 3
          ? "This check covers registration, tax and hiring requirements for sole proprietors in the City of Vancouver. It doesn't cover everything a business may need."
          : "We only use facts you confirm. Nothing read from your website or documents counts until you say so."}
      </p>
    </aside>
  );
}

function StepDot({ n, state }: { n: number; state: "done" | "current" | "todo" }) {
  if (state === "done") {
    return (
      <span className="inline-flex size-5 flex-none items-center justify-center rounded-full bg-brand text-white">
        <CheckIcon size={11} />
      </span>
    );
  }
  return (
    <span
      className={`inline-flex size-5 flex-none items-center justify-center rounded-full border-[1.5px] text-xs ${
        state === "current" ? "border-ink" : "border-step-off"
      }`}
    >
      {n}
    </span>
  );
}
