"""Config-driven scoring pass over the conversation transcript.

The rubric, threshold, verdict labels, and feedback prompt all come from the
scenario's `scoring` block — the engine only runs the loop and counts results.
"""

import json

from . import config


def transcript_text(scenario: dict, history: list) -> str:
    """Render history as labeled lines using the scenario's role names."""
    roles = scenario["roles"]
    lines = []
    for turn in history:
        label = roles["user_role"] if turn["role"] == "user" else roles["ai_role"]
        lines.append(f"{label}: {turn['text']}")
    return "\n".join(lines)


def run_scoring(client, scenario: dict, history: list) -> dict:
    """Return {'steps', 'met', 'total', 'passed', 'verdict', 'feedback'}."""
    sc = scenario["scoring"]
    roles = scenario["roles"]
    steps_txt = "\n".join(f"{i + 1}. {s}" for i, s in enumerate(sc["steps"]))
    prompt = sc["feedback_prompt"].format(
        transcript=transcript_text(scenario, history),
        steps=steps_txt,
        total=len(sc["steps"]),
        ai_role=roles["ai_role"],
        user_role=roles["user_role"],
    )
    result = client.chat.completions.create(
        model=config.MODEL_SCORING,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0,
    )
    data = json.loads(result.choices[0].message.content)

    steps = data.get("steps", [])
    # normalize: same length/order as the rubric, robust to a sloppy model
    normalized = []
    for i, rubric_step in enumerate(sc["steps"]):
        item = steps[i] if i < len(steps) and isinstance(steps[i], dict) else {}
        normalized.append({
            "step": rubric_step,
            "met": bool(item.get("met")),
            "note": str(item.get("note", "")),
        })
    met = sum(1 for s in normalized if s["met"])
    passed = met >= sc["threshold"]
    return {
        "steps": normalized,
        "met": met,
        "total": len(sc["steps"]),
        "passed": passed,
        "verdict": sc["pass_label"] if passed else sc["fail_label"],
        "feedback": str(data.get("feedback", "")),
    }
