// The data source behind /b/[id]: the FastAPI backend, or sample data for /b/demo.

import {
  ApiError,
  type BusinessProfile,
  type FactAnswers,
  type RequirementDetail,
  askChat,
  confirmProposal,
  getProfile,
  getQuestions,
  getRequirement,
  runAssessment,
} from "./api";
import { DEMO_ID, demoBackend } from "./demo";

export type Backend = {
  getProfile: typeof getProfile;
  runAssessment: typeof runAssessment;
  getQuestions: typeof getQuestions;
  getRequirement: (id: string) => Promise<RequirementDetail>;
  askChat: typeof askChat;
  confirmProposal: typeof confirmProposal;
  answerFacts: (businessId: string, answers: FactAnswers) => Promise<BusinessProfile>;
};

const liveBackend: Backend = {
  getProfile,
  runAssessment,
  getQuestions,
  getRequirement,
  askChat,
  confirmProposal,
  // The backend has no route for saving a direct answer yet (only proposals from intake or chat).
  answerFacts: () =>
    Promise.reject(new ApiError("Saving answers here isn't connected to the backend yet. Tell etika in chat instead.")),
};

export const backendFor = (businessId: string): Backend => (businessId === DEMO_ID ? demoBackend : liveBackend);
