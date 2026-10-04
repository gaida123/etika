// The data source behind /b/[id]: the FastAPI backend, or sample data for /b/demo.

import {
  type BusinessProfile,
  type DraftEmail,
  type FactAnswers,
  type RequirementDetail,
  askChat,
  confirmProposal,
  draftEmail,
  getAssessmentTrace,
  getProfile,
  getQuestions,
  getRequirement,
  runAssessment,
  updateProfile,
} from "./api";
import { DEMO_ID, demoBackend } from "./demo";

export type Backend = {
  getProfile: typeof getProfile;
  runAssessment: typeof runAssessment;
  getQuestions: typeof getQuestions;
  getRequirement: (id: string) => Promise<RequirementDetail>;
  getAssessmentTrace: typeof getAssessmentTrace;
  askChat: typeof askChat;
  confirmProposal: typeof confirmProposal;
  draftEmail: (businessId: string, requirementId: string) => Promise<DraftEmail>;
  answerFacts: (businessId: string, answers: FactAnswers) => Promise<BusinessProfile>;
};

const liveBackend: Backend = {
  getProfile,
  runAssessment,
  getQuestions,
  getRequirement,
  getAssessmentTrace,
  askChat,
  confirmProposal,
  draftEmail,
  answerFacts: updateProfile,
};

export const backendFor = (businessId: string): Backend => (businessId === DEMO_ID ? demoBackend : liveBackend);
