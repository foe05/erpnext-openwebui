"""Einstiegspunkt: startet den MCP-Server über stdio.

  python -m erpnext_connector

mcpo wickelt diesen stdio-Server für OpenWebUI in OpenAPI/HTTP ein; MCP-Clients
(Claude/Claude Code) sprechen ihn direkt an."""

from __future__ import annotations

from .server import mcp


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
