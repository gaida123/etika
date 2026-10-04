"use client";

import { useState } from "react";
import { EMPTY_ANSWERS, type IntakeAnswers } from "@/lib/intake";
import { Sidebar, type Step } from "./Sidebar";
import { StepActivities } from "./StepActivities";
import { StepBasics } from "./StepBasics";
import { StepConfirm } from "./StepConfirm";

export function IntakeWizard() {
  const [step, setStep] = useState<Step>(1);
  const [answers, setAnswers] = useState<IntakeAnswers>(EMPTY_ANSWERS);
  const [documents, setDocuments] = useState<File[]>([]);

  const update = (patch: Partial<IntakeAnswers>) => setAnswers((a) => ({ ...a, ...patch }));
  const goTo = (next: Step) => {
    setStep(next);
    window.scrollTo({ top: 0 });
  };

  return (
    <div className="shell">
      <Sidebar step={step} answers={answers} onGoTo={goTo} />
      <div className="content">
        {step === 1 && (
          <StepBasics
            answers={answers}
            update={update}
            onCancel={() => {
              setAnswers(EMPTY_ANSWERS);
              setDocuments([]);
            }}
            onNext={() => goTo(2)}
          />
        )}
        {step === 2 && (
          <StepActivities
            answers={answers}
            update={update}
            documents={documents}
            onDocumentsChange={setDocuments}
            onBack={() => goTo(1)}
            onNext={() => goTo(3)}
          />
        )}
        {step === 3 && (
          <StepConfirm
            answers={answers}
            update={update}
            documentCount={documents.length}
            onBack={() => goTo(2)}
            onEditStep={goTo}
          />
        )}
      </div>
    </div>
  );
}
