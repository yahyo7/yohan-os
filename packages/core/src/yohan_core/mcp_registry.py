"""MCP registry — load infra/mcp_registry.yaml and answer policy questions.

The registry is the one place that knows which servers exist, how to launch them,
and which tools require approval. Agents never hardcode tool lists (a brief
non-negotiable); they ask the registry.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

# infra/mcp_registry.yaml, resolved relative to the repo root.
_DEFAULT_PATH = (
    Path(__file__).resolve().parents[4] / "infra" / "mcp_registry.yaml"
)


@dataclass(frozen=True, slots=True)
class ToolSpec:
    name: str
    requires_approval: bool


@dataclass(frozen=True, slots=True)
class ServerSpec:
    name: str
    transport: str
    command: str
    args: list[str]
    env: dict[str, str]
    tools: dict[str, ToolSpec] = field(default_factory=dict)


class UnknownTool(KeyError):
    """Raised when a (server, tool) pair isn't declared in the registry."""


class Registry:
    def __init__(self, servers: dict[str, ServerSpec]) -> None:
        self._servers = servers

    @classmethod
    def load(cls, path: Path | str | None = None) -> "Registry":
        data = yaml.safe_load(Path(path or _DEFAULT_PATH).read_text()) or {}
        servers: dict[str, ServerSpec] = {}
        for name, spec in (data.get("servers") or {}).items():
            tools = {
                tname: ToolSpec(tname, bool(t.get("requires_approval", False)))
                for tname, t in (spec.get("tools") or {}).items()
            }
            servers[name] = ServerSpec(
                name=name,
                transport=spec.get("transport", "stdio"),
                command=spec["command"],
                args=list(spec.get("args", [])),
                env=dict(spec.get("env", {})),
                tools=tools,
            )
        return cls(servers)

    def server(self, name: str) -> ServerSpec:
        try:
            return self._servers[name]
        except KeyError:
            raise UnknownTool(f"no server '{name}' in registry") from None

    def tool(self, server: str, tool: str) -> ToolSpec:
        spec = self.server(server).tools.get(tool)
        if spec is None:
            raise UnknownTool(f"tool '{tool}' not declared for server '{server}'")
        return spec

    def requires_approval(self, server: str, tool: str) -> bool:
        return self.tool(server, tool).requires_approval
