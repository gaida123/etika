import { useState } from "react";
import { ChoiceGroup, Select } from "@/components/ui";
import {
  BUSINESS_TYPE_GROUPS,
  type BusinessType,
  type IntakeAnswers,
  OPEN_STATUSES,
  STRUCTURES,
  WORKPLACES,
  upcomingMonths,
} from "@/lib/intake";

type Props = {
  answers: IntakeAnswers;
  update: (patch: Partial<IntakeAnswers>) => void;
  onCancel: () => void;
  onNext: () => void;
};

export function StepBasics({ answers, update, onCancel, onNext }: Props) {
  const [months] = useState(() => upcomingMonths());
  const [showErrors, setShowErrors] = useState(false);
  const nameMissing = !answers.businessName.trim();

  return (
    <form
      className="inner flex flex-col gap-10"
      noValidate
      onSubmit={(e) => {
        e.preventDefault();
        if (nameMissing) return setShowErrors(true);
        onNext();
      }}
    >
      <div>
        <p className="pre">Step 1 of 3</p>
        <h1 className="hxl">Let&apos;s start with the basics.</h1>
        <p className="lead">
          A few details about your business so we know which rules to check. It takes about 5 minutes and you can
          change anything later.
        </p>
      </div>

      <div className="flex max-w-[520px] flex-col gap-2">
        <label htmlFor="bname" className="lbl">
          Business name
        </label>
        <input
          id="bname"
          className="inp"
          placeholder="Wick & Co"
          value={answers.businessName}
          onChange={(e) => update({ businessName: e.target.value })}
          aria-invalid={showErrors && nameMissing}
          aria-describedby="bname-hint"
        />
        {showErrors && nameMissing ? (
          <span id="bname-hint" className="text-sm text-[#a3341f]">
            Enter the name customers see so we can tailor the check.
          </span>
        ) : (
          <span id="bname-hint" className="hint">
            The name customers see. If it differs from your legal name, we&apos;ll ask about registering it.
          </span>
        )}
      </div>

      <div className="flex max-w-[520px] flex-col gap-2">
        <label htmlFor="btype" className="lbl">
          What kind of business is it?
        </label>
        <Select
          id="btype"
          value={answers.businessType ?? ""}
          onChange={(e) => update({ businessType: (e.target.value || null) as BusinessType | null })}
        >
          <option value="">Choose one</option>
          {BUSINESS_TYPE_GROUPS.map((g) => (
            <optgroup key={g.label} label={g.label}>
              {g.options.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </optgroup>
          ))}
        </Select>
      </div>

      <fieldset>
        <legend className="lbl">How is the business set up?</legend>
        <p className="hint mt-1 mb-3.5">Not sure? Pick &quot;Not sure&quot; and we&apos;ll flag anything that depends on it.</p>
        <ChoiceGroup
          name="struct"
          options={STRUCTURES}
          value={answers.structure}
          onChange={(structure) => update({ structure })}
        />
      </fieldset>

      <div className="flex flex-wrap gap-5">
        <div className="flex max-w-[360px] flex-[1_1_260px] flex-col gap-2">
          <label htmlFor="city" className="lbl">
            City
          </label>
          <Select id="city" value="vancouver" onChange={() => {}}>
            <option value="vancouver">City of Vancouver</option>
          </Select>
          <span className="hint">Only Vancouver is covered for now.</span>
        </div>
        <div className="flex flex-[2_1_320px] flex-col gap-2">
          <label htmlFor="addr" className="lbl">
            Street address
          </label>
          <input
            id="addr"
            className="inp"
            placeholder="Street address"
            autoComplete="street-address"
            value={answers.address}
            onChange={(e) => update({ address: e.target.value })}
          />
          <span className="hint">Some permits depend on the exact location. Working from home? Use your home address.</span>
        </div>
      </div>

      <fieldset>
        <legend className="lbl">Where do you run it from?</legend>
        <ChoiceGroup
          name="workplace"
          options={WORKPLACES}
          value={answers.workplace}
          onChange={(workplace) => update({ workplace })}
          className="mt-3.5 flex flex-wrap gap-2.5"
        />
        <p className="hint mt-2.5 mb-0">Home-based businesses and businesses with their own space follow different rules.</p>
      </fieldset>

      <fieldset>
        <legend className="lbl">Are you open yet?</legend>
        <ChoiceGroup
          name="open"
          options={OPEN_STATUSES}
          value={answers.openStatus}
          onChange={(openStatus) => update({ openStatus })}
          className="mt-3.5 flex flex-wrap items-center gap-2.5"
        >
          <label htmlFor="omonth" className="sr-only">
            Opening month
          </label>
          <span className="inline-block min-w-[180px]">
            <Select
              id="omonth"
              className="w-auto min-w-[180px]"
              disabled={answers.openStatus !== "soon"}
              value={answers.openingMonth}
              onChange={(e) => update({ openingMonth: e.target.value })}
            >
              <option value="">Month</option>
              {months.map((m) => (
                <option key={m.value} value={m.value}>
                  {m.label}
                </option>
              ))}
            </Select>
          </span>
        </ChoiceGroup>
        <p className="hint mt-2.5 mb-0">
          If you&apos;re not open yet, we&apos;ll put anything you need before opening at the top.
        </p>
      </fieldset>

      <div className="footer">
        <button type="button" className="btn btn-link" onClick={onCancel}>
          Cancel
        </button>
        <button type="submit" className="btn btn-p">
          Continue
        </button>
      </div>
    </form>
  );
}
