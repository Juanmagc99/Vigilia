from pathlib import Path
from jinja2 import Environment, FileSystemLoader, StrictUndefined

from app.schemas.incidents import IncidentDetail


class PromptRenderer:
    def __init__(self, templates_dir: Path) -> None:
        self._environment = Environment(
            loader=FileSystemLoader(templates_dir),
            undefined=StrictUndefined,
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def render_incident_report(self, incident: IncidentDetail) -> str:
        template = self._environment.get_template("incident_report.j2")
        return template.render(incident=incident)