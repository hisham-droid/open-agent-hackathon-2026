"""MemoryMiningService: turn runtime events into candidate memories.
With an injected generator it asks a model for a strict JSON array; without one (or if it fails) it stores direct
summaries as short-term memories, so sample mode works with no credentials."""
import json
import re
import uuid

KIND_TYPE = {"tool_result": "factual", "verdict": "procedural", "outcome": "procedural", "handoff": "factual"}


def parse_json_array(text):
    """Tolerate code fences and surrounding chatter. Returns a list of non-empty strings or None."""
    if not isinstance(text, str):
        return None
    text = re.sub(r"```[a-zA-Z]*", "", text)
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end <= start:
        return None
    try:
        arr = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None
    items = [s.strip() for s in arr if isinstance(s, str) and s.strip()]
    return items[:5] or None


def extraction_prompt(event):
    return ("Extract up to 3 durable memories from this agent event. Reply with a strict JSON array of short strings, "
            f"nothing else.\nEvent kind: {event['kind']}\nEvent: {event['summary']}")


def mine(store, event, agent_id, run_id, task_id, generator=None):
    contents, mode = None, "fallback"
    if generator is not None:
        try:
            contents = parse_json_array(generator(extraction_prompt(event)))
            mode = "model" if contents else "fallback"
        except Exception:
            contents, mode = None, "fallback"
    contents = contents or [event["summary"]]
    made = []
    for c in contents:
        rec = {"id": f"mem-{uuid.uuid4().hex[:10]}", "content": c, "type": KIND_TYPE.get(event["kind"], "general"),
               "layer": "short_term", "tags": [event["kind"], agent_id], "source": f"{agent_id}:{event['kind']}",
               "confidence": 0.5, "agentId": agent_id, "runId": run_id, "taskId": task_id}
        made.append(store.upsert(rec, actor=agent_id))
    return made, mode
