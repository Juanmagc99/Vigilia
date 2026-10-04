from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from vigilia.bootstrap.settings import Settings

RUNBOOKS = (
    ("payments-api", "payments-api.md", "CPU y memoria altas en payments-api"),
    ("payments", "payments.md", "Pagos indisponibles y pool de conexiones"),
    ("Grafana", "grafana.md", "Alertas de prueba y entrega del webhook"),
)
RUNBOOK_DIRECTORY = Path(__file__).parent / "runbooks"


def main() -> None:
    settings = Settings()
    if settings.api_token is None:
        raise SystemExit("Configura VIGILIA_API_TOKEN en el entorno o en .env")

    api_url = os.getenv("VIGILIA_API_URL", "http://localhost:8000").rstrip("/")
    api_token = settings.api_token.get_secret_value()

    for service, filename, title in RUNBOOKS:
        content = (RUNBOOK_DIRECTORY / filename).read_text(encoding="utf-8")
        payload = {
            "service": service,
            "source": f"scripts/runbooks/{filename}",
            "title": title,
            "version": "1.0",
            "content": content,
        }
        request = Request(
            f"{api_url}/knowledge/documents",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=90) as response:
                result = json.loads(response.read())
        except HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            raise SystemExit(
                f"No se pudo cargar {filename}: HTTP {exc.code}: {details}"
            ) from exc
        except URLError as exc:
            raise SystemExit(
                f"No se pudo conectar con Vigilia en {api_url}: {exc}"
            ) from exc

        print(
            f"{service}: documento {result['id']} cargado "
            f"({result['chunks']} fragmentos)"
        )


if __name__ == "__main__":
    main()
