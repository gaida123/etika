import { useRouter } from "next/navigation";
import { useState } from "react";
import { CheckIcon } from "@/components/ui";
import { ApiError, createProfile } from "@/lib/api";
import {
  type IntakeAnswers,
  QUICK_ANSWERS,
  type QuickAnswer,
  factRows,
  quickQuestions,
  toProfileCreate,
} from "@/lib/intake";

type Props = {
  answers: IntakeAnswers;
  update: (patch: Partial<IntakeAnswers>) => void;
  documentCount: number;
  onBack: () => void;
  onEditStep: (step: 1 | 2) => void;
};

type SubmitState =
  | { kind: "idle" }
  | { kind: "saving" }
  | { kind: "error"; message: string };

const COUNT_WORDS = ["No", "One", "Two"];

export function StepConfirm({ answers, update, documentCount, onBack, onEditStep }: Props) {
  const router = useRouter();
  const [submit, setSubmit] = useState<SubmitState>({ kind: "idle" });
  const rows = factRows(answers);
  const answered = rows.filter((r) => r.value).length;
  const questions = quickQuestions(answers);

  async function run() {
    setSubmit({ kind: "saving" });
    try {
      const profile = await createProfile(toProfileCreate(answers));
      router.push(`/b/${profile.business_id}`);
    } catch (e) {
      setSubmit({ kind: "error", message: e instanceof ApiError ? e.message : "Something went wrong. Try again." });
    }
  }

  return (
    <main className="inner flex flex-col gap-8">
      <div>
        <p className="pre">Step 3 of 3</p>
        <h1 className="hxl">Check what we understood.</h1>
        <p className="lead">Your results are only as good as these facts. Confirm or fix anything that&apos;s off.</p>
      </div>

      <section className="box overflow-hidden" aria-labelledby="facts-h">
        <div className="flex flex-wrap items-center justify-between gap-2 bg-panel px-5 py-4">
          <h2 id="facts-h" className="m-0 text-[17px] font-medium">
            Business facts
          </h2>
          <span className="hint">
            {answered} confirmed
            {rows.length > answered && `, ${rows.length - answered} not answered`}
          </span>
        </div>
        {rows.map((r) => (
          <div key={r.label} className="row">
            <div className="min-w-0 flex-[1_1_200px]">
              <div className="muted text-[13px]">{r.label}</div>
              <div className={r.value ? "font-medium" : "muted"}>{r.value ?? "Not answered"}</div>
            </div>
            {r.value ? (
              <span className="ok">
                <CheckIcon />
                Confirmed
              </span>
            ) : (
              <button type="button" className="btn btn-link min-h-9 px-3 text-sm" onClick={() => onEditStep(r.step)}>
                Answer
              </button>
            )}
          </div>
        ))}
        {documentCount > 0 && (
          <div className="row bg-brand-tint">
            <div className="min-w-0 flex-[1_1_200px]">
              <div className="muted text-[13px]">Documents</div>
              <div className="font-medium">
                {documentCount} {documentCount === 1 ? "file" : "files"} attached
              </div>
              <div className="muted mt-0.5 text-[13px]">
                Reading documents isn&apos;t connected yet, so nothing from them is used.
              </div>
            </div>
          </div>
        )}
      </section>

      {questions.length > 0 && (
        <section className="box flex flex-col gap-[22px] p-6" aria-labelledby="q-h">
          <div>
            <h2 id="q-h" className="h2 mb-1">
              {COUNT_WORDS[questions.length]} quick {questions.length === 1 ? "question" : "questions"}
            </h2>
            <p className="hint m-0">
              Answer now or skip. Skipped questions show up in your results as &quot;Needs your input&quot; instead of a
              guess.
            </p>
          </div>
          {questions.map((q) => {
            const value = answers[q.key];
            return (
              <fieldset key={q.key}>
                <legend className="font-medium">{q.question}</legend>
                <div className="muted mt-0.5 mb-2.5 text-[13px]">Affects: {q.affects}</div>
                <div className="flex flex-wrap items-center gap-2">
                  {QUICK_ANSWERS.map((o) => (
                    <label key={o.value} className="opt">
                      <input
                        type="radio"
                        name={q.key}
                        checked={value === o.value}
                        onChange={() => update({ [q.key]: o.value as QuickAnswer })}
                      />
                      {o.label}
                    </label>
                  ))}
                  {value === "skipped" ? (
                    <span className="hint px-2">Skipped for now</span>
                  ) : (
                    <button type="button" className="btn btn-link" onClick={() => update({ [q.key]: "skipped" })}>
                      Skip for now
                    </button>
                  )}
                </div>
              </fieldset>
            );
          })}
        </section>
      )}

      <div className="footer">
        <button type="button" className="btn btn-soft" onClick={onBack}>
          Back
        </button>
        <div className="flex flex-wrap items-center gap-4">
          <span className="hint" role={submit.kind === "error" ? "alert" : undefined}>
            {submit.kind === "error" ? (
              <span className="text-[#a3341f]">{submit.message}</span>
            ) : (
              "Unconfirmed facts won't be used."
            )}
          </span>
          <button type="button" className="btn btn-p" disabled={submit.kind === "saving"} onClick={run}>
            {submit.kind === "saving" ? "Saving…" : "Run my check"}
          </button>
        </div>
      </div>
    </main>
  );
}
