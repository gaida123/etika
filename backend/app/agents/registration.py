"""Registration and licensing agent: "Am I allowed to exist and operate here?"."""

from app.agents.base import BaseAgent


class RegistrationAgent(BaseAgent):
    """Owns business name registration, the Vancouver business licence and the CRA business number."""

    name = "registration"
    title = "Registration and Licensing specialist"
    specialist_prompt = """\
You cover: registering a business name with BC Registries, the City of Vancouver business licence,
and the CRA business number.
Gray areas to flag (never resolve):
- Home-based or online-only businesses and whether/how the Vancouver licence applies.
- Owners trading under their own name plus a tagline or descriptor.
The business number is needed before GST or payroll accounts; explain that ordering when relevant."""
