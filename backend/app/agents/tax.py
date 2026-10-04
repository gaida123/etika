"""Tax registration agent: "Do I have to charge tax, and when?"."""

from app.agents.base import BaseAgent


class TaxAgent(BaseAgent):
    """Owns BC PST, GST, voluntary GST and charging tax correctly once registered."""

    name = "tax"
    title = "Tax Registration specialist"
    tool_names = (
        "retrieve_evidence",
        "get_requirement",
        "get_profile_fact",
        "get_calculator_result",
        "flag_for_review",
    )
    specialist_prompt = """\
You cover: BC PST registration, GST registration, voluntary GST registration, and charging and
showing tax correctly once registered.
The PST small seller test and GST small supplier test are run by code calculators. Report their
outcomes and numbers exactly as given; any crossing month is an estimate and must be called one.
Gray areas to flag (never resolve):
- Goods vs services split (PST mostly applies to goods; some professional services since Oct 1, 2026).
- Regular sales at markets or fairs and the "no established business premises" condition.
- Revenue data missing or incomplete."""

    def investigate_instructions(self) -> str:
        return "Call get_calculator_result for pst_small_seller_test and gst_small_supplier_test."
