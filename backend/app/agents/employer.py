"""Employer obligations agent: "What changes the day I hire someone?"."""

from app.agents.base import BaseAgent


class EmployerAgent(BaseAgent):
    """Owns WorkSafeBC, payroll account, minimum wage, pay statements, payroll records, worker status."""

    name = "employer"
    title = "Employer Obligations specialist"
    max_tool_calls = 8
    specialist_prompt = """\
You cover: WorkSafeBC registration, the CRA payroll account, minimum wage, pay statements,
payroll records, and employee vs contractor status.
Gray areas to flag (never resolve):
- Whether a worker is an employee or a contractor. Explain the question and recommend checking.
- Family members helping out in the business."""

    def mode_instructions(self, mode: str | None) -> str:
        if mode == "full":
            return "Mode: full. The owner has employees. Explain what applies to them now."
        return (
            "Mode: pre-hire. The owner has not hired yet, or their hiring plans are unknown. "
            "Explain what switches on the day they hire their first employee."
        )
