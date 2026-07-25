"""Konfiguration aus der Umgebung laden.

Secrets (API-Key/Secret) kommen ausschließlich aus Umgebungsvariablen bzw.
einem Secret-Store — niemals aus dem Quelltext. Für lokale Entwicklung wird
optional eine .env-Datei eingelesen (die nicht committet wird)."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

# Lädt .env für lokale Entwicklung; in Produktion setzt der Betrieb echte
# Umgebungsvariablen und die .env fehlt schlicht.
load_dotenv()


class ConfigError(RuntimeError):
    """Fehlende oder ungültige Konfiguration."""


@dataclass(frozen=True)
class Settings:
    base_url: str
    api_key: str
    api_secret: str
    default_limit: int = 20
    timeout: float = 30.0
    # Selling-Config-Vorbedingungen (Phase 1 ⇄ Phase 3). Optional — fehlen sie,
    # warnen die Verben, statt still falsche Beträge/Belege zu erzeugen.
    default_employee: str = ""
    generic_service_item: str = ""
    default_tax_template: str = ""
    default_price_list: str = ""

    @property
    def auth_header(self) -> str:
        """ERPNext/Frappe-Token-Auth: 'token <key>:<secret>'."""
        return f"token {self.api_key}:{self.api_secret}"


def _require(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ConfigError(
            f"Umgebungsvariable {name} fehlt. Siehe .env.example — "
            "Secrets gehören in die Umgebung, nicht in den Code."
        )
    return value


def load_settings() -> Settings:
    """Liest die Konfiguration aus der Umgebung und validiert sie."""
    base_url = _require("ERPNEXT_URL").rstrip("/")
    return Settings(
        base_url=base_url,
        api_key=_require("ERPNEXT_API_KEY"),
        api_secret=_require("ERPNEXT_API_SECRET"),
        default_limit=int(os.environ.get("ERPNEXT_DEFAULT_LIMIT", "20")),
        timeout=float(os.environ.get("ERPNEXT_TIMEOUT", "30")),
        default_employee=os.environ.get("ERPNEXT_DEFAULT_EMPLOYEE", "").strip(),
        generic_service_item=os.environ.get("ERPNEXT_GENERIC_SERVICE_ITEM", "").strip(),
        default_tax_template=os.environ.get("ERPNEXT_DEFAULT_TAX_TEMPLATE", "").strip(),
        default_price_list=os.environ.get("ERPNEXT_DEFAULT_PRICE_LIST", "").strip(),
    )
