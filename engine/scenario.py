"""Scenario config layer: discovery, validation, and prompt assembly.

A scenario is DATA (one module in `scenarios/` exporting a `SCENARIO` dict).
The engine consumes only the schema below and never hardcodes scenario content.
Adding a use case = adding one file in `scenarios/` — no engine edit.

Schema (all required unless noted):
    id, title, language            str (language = display language code, e.g. "id")
    roles                          {"ai_role": str, "user_role": str}
    briefing                       str, may use placeholders below
    opening                        str, first-turn guidance for the AI persona
    instruction_template           str, persona system prompt with placeholders
    personas                       list of dicts:
        key, name, avatar, color, mood, voice, voice_instructions,
        scenario_brief, goal, deescalation (optional)
    scoring                        {"steps": [str, ...], "threshold": int,
                                    "pass_label": str, "fail_label": str,
                                    "feedback_prompt": str}

Placeholders available in briefing / opening / instruction_template:
    {name} {avatar} {mood} {scenario_brief} {goal} {deescalation}
    {ai_role} {user_role}
feedback_prompt placeholders: {transcript} {steps} {total} {ai_role} {user_role}
"""

import importlib
import pkgutil

import scenarios as _scenarios_pkg


class ScenarioError(Exception):
    """A scenario config is missing or malformed — fail loudly, don't half-run."""


_REQUIRED_TOP = [
    "id", "title", "language", "roles", "briefing", "opening",
    "instruction_template", "personas", "scoring",
]
_REQUIRED_PERSONA = [
    "key", "name", "avatar", "color", "mood", "voice",
    "voice_instructions", "scenario_brief", "goal",
]
_REQUIRED_SCORING = ["steps", "threshold", "pass_label", "fail_label", "feedback_prompt"]


def validate_scenario(sc: dict, source: str) -> None:
    missing = [k for k in _REQUIRED_TOP if k not in sc]
    if missing:
        raise ScenarioError(f"scenario '{source}': missing top-level keys {missing}")
    for role_key in ("ai_role", "user_role"):
        if role_key not in sc["roles"]:
            raise ScenarioError(f"scenario '{source}': roles missing '{role_key}'")
    if not sc["personas"]:
        raise ScenarioError(f"scenario '{source}': personas list is empty")
    for p in sc["personas"]:
        p_missing = [k for k in _REQUIRED_PERSONA if k not in p]
        if p_missing:
            raise ScenarioError(
                f"scenario '{source}': persona '{p.get('key', '?')}' missing keys {p_missing}"
            )
    s_missing = [k for k in _REQUIRED_SCORING if k not in sc["scoring"]]
    if s_missing:
        raise ScenarioError(f"scenario '{source}': scoring missing keys {s_missing}")
    scoring = sc["scoring"]
    if not scoring["steps"]:
        raise ScenarioError(f"scenario '{source}': scoring.steps is empty")
    if not isinstance(scoring["threshold"], int) or not (
        1 <= scoring["threshold"] <= len(scoring["steps"])
    ):
        raise ScenarioError(
            f"scenario '{source}': scoring.threshold must be an int between 1 and "
            f"{len(scoring['steps'])}"
        )


def load_scenarios() -> dict:
    """Discover, validate, and return all scenarios as {id: SCENARIO}."""
    found = {}
    for mod_info in pkgutil.iter_modules(_scenarios_pkg.__path__):
        module = importlib.import_module(f"scenarios.{mod_info.name}")
        sc = getattr(module, "SCENARIO", None)
        if sc is None:
            continue
        validate_scenario(sc, mod_info.name)
        if sc["id"] in found:
            raise ScenarioError(f"duplicate scenario id '{sc['id']}' in '{mod_info.name}'")
        found[sc["id"]] = sc
    if not found:
        raise ScenarioError("no scenario configs found in scenarios/")
    return found


def _context(scenario: dict, persona: dict) -> dict:
    ai_role = scenario["roles"]["ai_role"]
    user_role = scenario["roles"]["user_role"]

    def _roles(text: str) -> str:
        # persona fields may reference the roles; expand them (non-recursive .format
        # would otherwise leave them as literal "{user_role}")
        return text.replace("{ai_role}", ai_role).replace("{user_role}", user_role)

    return {
        "name": persona["name"],
        "avatar": persona["avatar"],
        "mood": _roles(persona["mood"]),
        "scenario_brief": _roles(persona["scenario_brief"]),
        "goal": _roles(persona["goal"]),
        "deescalation": _roles(persona.get("deescalation", "")),
        "ai_role": ai_role,
        "user_role": user_role,
    }


def format_text(text: str, scenario: dict, persona: dict) -> str:
    """Fill scenario placeholders in briefing/opening text."""
    return text.format(**_context(scenario, persona))


def build_instructions(scenario: dict, persona: dict) -> str:
    """Assemble the persona system prompt for the chained LLM path."""
    return scenario["instruction_template"].format(**_context(scenario, persona))


def build_realtime_instructions(scenario: dict, persona: dict) -> str:
    """Persona prompt for the Realtime session: base instructions + voice style
    + opening behavior (the persona speaks first when the session starts)."""
    parts = [
        build_instructions(scenario, persona),
        f"Voice style: {persona['voice_instructions']}",
        format_text(scenario["opening"], scenario, persona),
    ]
    return "\n\n".join(parts)
