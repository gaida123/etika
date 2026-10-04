import { useRef, useState } from "react";
import { ChoiceGroup, Select, UploadIcon } from "@/components/ui";
import {
  ACTIVITIES,
  type Activity,
  EXPECTED_SALES,
  type ExpectedSales,
  type IntakeAnswers,
  ONLINE,
  OUT_OF_SCOPE_ACTIVITIES,
  STAFF,
  salesLabel,
  upcomingMonths,
} from "@/lib/intake";

type Props = {
  answers: IntakeAnswers;
  update: (patch: Partial<IntakeAnswers>) => void;
  documents: File[];
  onDocumentsChange: (files: File[]) => void;
  onBack: () => void;
  onNext: () => void;
};

export function StepActivities({ answers, update, documents, onDocumentsChange, onBack, onNext }: Props) {
  const name = answers.businessName.trim() || "your business";
  const [months] = useState(() => upcomingMonths(12));
  const outOfScope = answers.activities.some((v) => OUT_OF_SCOPE_ACTIVITIES.includes(v));

  const toggleActivity = (value: Activity, on: boolean) =>
    update({
      activities: on
        ? ACTIVITIES.map((a) => a.value).filter((v) => v === value || answers.activities.includes(v))
        : answers.activities.filter((v) => v !== value),
    });

  return (
    <form
      className="inner flex flex-col gap-10"
      onSubmit={(e) => {
        e.preventDefault();
        onNext();
      }}
    >
      <div>
        <p className="pre">Step 2 of 3</p>
        <h1 className="hxl">What does {name} do day to day?</h1>
        <p className="lead">
          We use this to work out which licences, permits and registrations may apply. You can change any answer later.
        </p>
      </div>

      <fieldset>
        <legend className="lbl">
          Activities <span className="muted font-normal">(select all that apply)</span>
        </legend>
        <div className="mt-3.5 grid grid-cols-[repeat(auto-fill,minmax(250px,1fr))] gap-2.5">
          {ACTIVITIES.map((a) => (
            <label key={a.value} className="opt">
              <input
                type="checkbox"
                checked={answers.activities.includes(a.value)}
                onChange={(e) => toggleActivity(a.value, e.target.checked)}
              />
              {a.label}
            </label>
          ))}
        </div>
        {outOfScope && (
          <p className="hint mt-2.5 mb-0">
            Food safety, liquor and patio permits aren&apos;t covered by this check yet. We&apos;ll still check
            registration, tax and hiring.
          </p>
        )}
      </fieldset>

      <fieldset>
        <legend className="lbl">Does anyone besides you work in the business?</legend>
        <p className="hint mt-1 mb-3.5">Include part-time staff, family on payroll, and anyone starting soon.</p>
        <ChoiceGroup name="staff" options={STAFF} value={answers.staff} onChange={(staff) => update({ staff })}>
          {answers.staff === "planning" && (
            <span className="inline-block min-w-[180px]">
              <label htmlFor="hmonth" className="sr-only">
                Month you plan to hire
              </label>
              <Select
                id="hmonth"
                className="w-auto min-w-[180px]"
                value={answers.plannedHireMonth}
                onChange={(e) => update({ plannedHireMonth: e.target.value })}
              >
                <option value="">Month (optional)</option>
                {months.map((m) => (
                  <option key={m.value} value={m.value}>
                    {m.label}
                  </option>
                ))}
              </Select>
            </span>
          )}
        </ChoiceGroup>
      </fieldset>

      <fieldset>
        <legend className="lbl">Do you sell online?</legend>
        <ChoiceGroup
          name="online"
          options={ONLINE}
          value={answers.online}
          onChange={(online) => update({ online })}
          className="mt-3.5 flex flex-wrap gap-2.5"
        />
      </fieldset>

      <div className="flex max-w-[420px] flex-col gap-2">
        <label htmlFor="sales" className="lbl">
          {salesLabel(answers)}
        </label>
        <Select
          id="sales"
          value={answers.expectedSales}
          onChange={(e) => update({ expectedSales: e.target.value as ExpectedSales })}
        >
          {EXPECTED_SALES.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </Select>
        <span className="hint">
          Some tax registrations depend on this. &quot;Not sure&quot; is fine. We&apos;ll flag it instead of guessing.
        </span>
      </div>

      <section className="box flex flex-col gap-[18px] bg-panel p-6" aria-labelledby="opt-h">
        <div>
          <div className="muted text-[13px]">Optional</div>
          <h2 id="opt-h" className="h2 mt-0.5">
            Speed things up with what you already have
          </h2>
        </div>
        <div className="flex flex-col gap-1.5">
          <label htmlFor="site" className="font-medium">
            Website
          </label>
          <input
            id="site"
            className="inp max-w-[420px]"
            inputMode="url"
            autoComplete="url"
            placeholder="wickandco.example"
            value={answers.website}
            onChange={(e) => update({ website: e.target.value })}
          />
        </div>
        <DocumentDrop files={documents} onChange={onDocumentsChange} />
        <p className="hint m-0">Anything we read from these, you confirm on the next step before it&apos;s used.</p>
      </section>

      <div className="footer">
        <button type="button" className="btn btn-soft" onClick={onBack}>
          Back
        </button>
        <button type="submit" className="btn btn-p">
          Continue
        </button>
      </div>
    </form>
  );
}

function DocumentDrop({ files, onChange }: { files: File[]; onChange: (files: File[]) => void }) {
  const input = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const add = (list: FileList | null) => {
    if (!list?.length) return;
    const known = new Set(files.map((f) => `${f.name}:${f.size}`));
    onChange([...files, ...Array.from(list).filter((f) => !known.has(`${f.name}:${f.size}`))]);
  };

  return (
    <div className="flex flex-col gap-2">
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          add(e.dataTransfer.files);
        }}
        className={`flex min-h-[120px] flex-col items-center justify-center gap-1.5 rounded-[2px] border border-dashed p-4 text-center ${
          dragging ? "border-brand bg-brand-tint" : "border-field bg-white"
        }`}
      >
        <span className="text-brand">
          <UploadIcon />
        </span>
        <div className="font-medium">Drop a licence, permit, certificate or lease</div>
        <div className="hint">
          PDF or photo, or{" "}
          <button
            type="button"
            className="cursor-pointer border-0 bg-transparent p-0 text-brand underline underline-offset-[3px]"
            onClick={() => input.current?.click()}
          >
            browse files
          </button>
        </div>
        <input
          ref={input}
          type="file"
          multiple
          accept="application/pdf,image/*"
          className="sr-only"
          tabIndex={-1}
          onChange={(e) => {
            add(e.target.files);
            e.target.value = "";
          }}
        />
      </div>
      {files.length > 0 && (
        <ul className="m-0 flex list-none flex-col gap-1 p-0 text-sm">
          {files.map((f) => (
            <li key={`${f.name}:${f.size}`} className="flex items-center justify-between gap-3">
              <span className="truncate">{f.name}</span>
              <button
                type="button"
                className="muted cursor-pointer border-0 bg-transparent p-0 underline underline-offset-[3px]"
                onClick={() => onChange(files.filter((x) => x !== f))}
              >
                Remove
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
