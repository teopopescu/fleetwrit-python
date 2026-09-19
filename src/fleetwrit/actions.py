"""Action definitions, display hints, and JSON-schema derivation.

``@action`` decorates the function that performs a consequential action. It
derives an args JSON Schema from type hints, versions it by hashing that
schema, and attaches ``.action(**kwargs)`` to build a bound :class:`Action`.
"""

from __future__ import annotations

import hashlib
import inspect
from dataclasses import dataclass, field
from typing import Any, Callable, Literal, TypeVar, get_type_hints

from .fingerprint import canonicalize, fingerprint

Risk = Literal["low", "medium", "high", "critical"]

# --- Display hints ---------------------------------------------------------


@dataclass(frozen=True)
class Money:
    """Render an integer arg (minor units) as money, using ``currency_field``."""

    currency_field: str | None = None


@dataclass(frozen=True)
class Diff:
    """Render an arg as a before/after diff."""


@dataclass(frozen=True)
class Code:
    """Render an arg as a code block, optionally with a language."""

    language: str | None = None


@dataclass(frozen=True)
class Link:
    """Render an arg as a hyperlink."""


@dataclass(frozen=True)
class Table:
    """Render an arg as a table."""


DisplayHint = Money | Diff | Code | Link | Table

# --- JSON Schema derivation ------------------------------------------------

_JSON_TYPES: dict[type, str] = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    dict: "object",
    list: "array",
}


def _json_type(annotation: Any) -> str:
    if isinstance(annotation, type):
        return _JSON_TYPES.get(annotation, "string")
    return "string"


def derive_schema(fn: Callable[..., Any]) -> dict[str, Any]:
    """Derive a JSON Schema (draft 2020-12) for a function's parameters."""
    try:
        hints = get_type_hints(fn)
    except Exception:
        hints = {}
    sig = inspect.signature(fn)
    properties: dict[str, Any] = {}
    required: list[str] = []
    for name, param in sig.parameters.items():
        if name in ("self", "cls") or param.kind in (
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        ):
            continue
        annotation = hints.get(name, str)
        properties[name] = {"type": _json_type(annotation)}
        if param.default is inspect.Parameter.empty:
            required.append(name)
    schema: dict[str, Any] = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "properties": properties,
        "additionalProperties": False,
    }
    if required:
        schema["required"] = required
    return schema


def schema_version(schema: dict[str, Any]) -> str:
    """Version = first 8 hex chars of sha256 over the canonical schema."""
    digest = hashlib.sha256(canonicalize(schema).encode("utf-8")).hexdigest()
    return digest[:8]


# --- Action ----------------------------------------------------------------


@dataclass
class Action:
    """One concrete action instance: a type, its args, and identity metadata.

    ``fingerprint`` is computed from the action identity plus the agent's id
    and environment. An undeclared action can be built directly as
    ``Action(type=..., args=...)``.
    """

    type: str
    args: dict[str, Any] = field(default_factory=dict)
    version: str = "0"
    tool: str | None = None
    reversible: bool = True
    title: str | None = None
    summary: str | None = None
    risk: Risk = "medium"
    queue: str | None = None
    editable: list[str] = field(default_factory=list)
    display: dict[str, DisplayHint] = field(default_factory=dict)
    redact: list[str] = field(default_factory=list)

    def fingerprint(self, agent_id: str, environment: str) -> str:
        """Return this action's fingerprint bound to an agent and environment."""
        return fingerprint(
            type=self.type,
            version=self.version,
            tool=self.tool,
            args=self.args,
            agent_id=agent_id,
            environment=environment,
        )

    def rendered_summary(self) -> str | None:
        """Fill the ``summary`` template with the action's args."""
        if self.summary is None:
            return None
        try:
            return self.summary.format(**self.args)
        except (KeyError, IndexError):
            return self.summary


# --- @action decorator -----------------------------------------------------

F = TypeVar("F", bound=Callable[..., Any])


class ActionDefinition:
    """A registered action type: metadata, derived schema, and version.

    Wraps the decorated function. Call it to run the action; call
    ``.action(**kwargs)`` to build a bound :class:`Action` for a request.
    """

    def __init__(
        self,
        fn: Callable[..., Any],
        *,
        type: str,
        title: str,
        summary: str,
        risk: Risk = "medium",
        reversible: bool = True,
        queue: str | None = None,
        expires_in: str | None = None,
        on_expiry: str | None = None,
        display: dict[str, DisplayHint] | None = None,
        editable: list[str] | None = None,
        redact: list[str] | None = None,
        subjects: list[str] | None = None,
        owner: str | None = None,
        tool: str | None = None,
        ask_when: Callable[[Action], bool] | None = None,
    ) -> None:
        self._fn = fn
        self.type = type
        self.title = title
        self.summary = summary
        self.risk: Risk = risk
        self.reversible = reversible
        self.queue = queue
        self.expires_in = expires_in
        self.on_expiry = on_expiry
        self.display = display or {}
        self.editable = editable or []
        self.redact = redact or []
        self.subjects = subjects or []
        self.owner = owner
        self.tool = tool or f"{fn.__module__}.{fn.__qualname__}"
        self.ask_when = ask_when
        self.schema = derive_schema(fn)
        self.version = schema_version(self.schema)
        self.__doc__ = fn.__doc__
        self.__name__ = getattr(fn, "__name__", type)

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self._fn(*args, **kwargs)

    def _validate(self, args: dict[str, Any]) -> None:
        required = set(self.schema.get("required", []))
        missing = required - set(args)
        if missing:
            raise TypeError(f"action {self.type!r} missing args: {sorted(missing)}")
        allowed = set(self.schema.get("properties", {}))
        unknown = set(args) - allowed
        if unknown:
            raise TypeError(f"action {self.type!r} got unknown args: {sorted(unknown)}")

    def action(self, **kwargs: Any) -> Action:
        """Build a bound :class:`Action` from keyword args, validated by schema."""
        self._validate(kwargs)
        return Action(
            type=self.type,
            args=dict(kwargs),
            version=self.version,
            tool=self.tool,
            reversible=self.reversible,
            title=self.title,
            summary=self.summary,
            risk=self.risk,
            queue=self.queue,
            editable=list(self.editable),
            display=dict(self.display),
            redact=list(self.redact),
        )

    def definition(self) -> dict[str, Any]:
        """Return the catalog record uploaded by ``Client.register``."""
        return {
            "type": self.type,
            "version": self.version,
            "title": self.title,
            "summary": self.summary,
            "risk": self.risk,
            "reversible": self.reversible,
            "queue": self.queue,
            "editable": list(self.editable),
            "owner": self.owner,
            "tool": self.tool,
            "schema": self.schema,
        }


def action(
    *,
    type: str,
    title: str,
    summary: str,
    risk: Risk = "medium",
    reversible: bool = True,
    queue: str | None = None,
    expires_in: str | None = None,
    on_expiry: str | None = None,
    display: dict[str, DisplayHint] | None = None,
    editable: list[str] | None = None,
    redact: list[str] | None = None,
    subjects: list[str] | None = None,
    owner: str | None = None,
    tool: str | None = None,
    ask_when: Callable[[Action], bool] | None = None,
) -> Callable[[F], ActionDefinition]:
    """Decorator that turns a function into an :class:`ActionDefinition`."""

    def wrap(fn: F) -> ActionDefinition:
        return ActionDefinition(
            fn,
            type=type,
            title=title,
            summary=summary,
            risk=risk,
            reversible=reversible,
            queue=queue,
            expires_in=expires_in,
            on_expiry=on_expiry,
            display=display,
            editable=editable,
            redact=redact,
            subjects=subjects,
            owner=owner,
            tool=tool,
            ask_when=ask_when,
        )

    return wrap
