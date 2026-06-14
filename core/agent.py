"""Keystone's review assistant: a REAL bounded tool-using agent, off the trust path.

This is the agentic layer the hackathon asks for, built so it can NEVER corrupt the
deterministic guarantees. The LLM is given THREE tools, each a thin wrapper over the
deterministic engine:

    blast_radius(symbol)      -> tier / action / counts / approvers / signature
    precedent(symbol)         -> prior approvals, rejections, signature-identical contradiction
    propose_reviewers(symbol) -> prior approvers + the policy-required owner

It runs a short ReAct-style loop (model -> tool_call -> deterministic result -> model)
for up to MAX_STEPS, then must answer in 2-4 sentences with a recommended NEXT STEP.
Hard invariants:
  - Every number in every tool result is computed by core/impact.py / core/audit.py.
    The model only chooses which tool to call and explains the results; it cannot
    invent a count, a tier, or a signature.
  - The model PROPOSES. It never records a decision. The verdict stays with the human
    and the deterministic gate (core/gate.py). The returned `answer` is advisory prose.
  - No key / no quota / no tool support -> a deterministic plan runs the same tools in a
    fixed order and composes a template recommendation, so the assistant always works
    (clearly labeled deterministic). The deterministic path is governance-equivalent by
    design: the agent's value is explanation and triage, not authority.

Standard library only (the LLM transport lives in core/llm.py).
"""
from __future__ import annotations

from typing import Optional

from . import impact as impact_mod, policy as policy_mod, llm as llm_mod

MAX_STEPS = int(__import__("os").environ.get("KEYSTONE_AGENT_MAX_STEPS", "4"))

_SYSTEM = (
    "You are Keystone's governed-review assistant. A human reviewer is deciding whether to "
    "approve a code change. Use the provided tools to gather FACTS about the change's blast "
    "radius, governance tier, and prior decisions, then give the reviewer a short, concrete "
    "recommendation. Strict rules: (1) call tools to get every number — never guess or invent "
    "a count, tier, name, or signature; (2) you do NOT decide — recommend a next step "
    "(approve with a stated reason / get a second approver / pull in the required owner / file "
    "an RFC / override with accountability) and let the human and the deterministic gate decide; "
    "(3) answer in 2 to 4 plain sentences, no markdown, no lists. When you have enough facts, "
    "stop calling tools and give the recommendation."
)

# OpenAI-compatible tool schemas exposed to the model.
TOOL_SCHEMAS = [
    {"type": "function", "function": {
        "name": "blast_radius",
        "description": "Deterministic blast radius and governance tier for a symbol from the Orbit code graph.",
        "parameters": {"type": "object", "properties": {
            "symbol": {"type": "string", "description": "the symbol/definition name to analyze"}},
            "required": ["symbol"]}}},
    {"type": "function", "function": {
        "name": "precedent",
        "description": "Prior governed decisions on a symbol: approvals, rejections, and any signature-identical contradiction.",
        "parameters": {"type": "object", "properties": {
            "symbol": {"type": "string"}}, "required": ["symbol"]}}},
    {"type": "function", "function": {
        "name": "propose_reviewers",
        "description": "Suggested reviewers for a symbol: who approved it before and the policy-required owner.",
        "parameters": {"type": "object", "properties": {
            "symbol": {"type": "string"}}, "required": ["symbol"]}}},
]


class ReviewTools:
    """Deterministic tool executor bound to one graph + ledger. Every method returns a
    plain dict of engine-computed facts; nothing here calls a model or invents a value."""

    def __init__(self, graph, ledger, max_depth: int = 3):
        self.g = graph
        self.led = ledger
        self.max_depth = max_depth

    def _impact_and_policy(self, symbol: str):
        imp = impact_mod.compute_blast_radius(self.g, symbol, max_depth=self.max_depth)
        if imp is None:
            return None, None, None
        d = imp.to_dict()
        prec = self.led.precedent(target_symbols=[symbol], signature=imp.signature,
                                  target_fqns=[imp.epicenter_fqn] if imp.epicenter_fqn else None)
        pol = policy_mod.evaluate(d, prec)
        return imp, d, pol

    def blast_radius(self, symbol: str) -> dict:
        imp, d, pol = self._impact_and_policy(symbol)
        if imp is None:
            return {"error": f"no symbol named {symbol} in the graph"}
        ic, pc = d["counts"], pol["counts"]   # impact rings vs policy file/dir rollup
        return {"symbol": symbol, "epicenter": d["epicenter"].get("fqn") or d["epicenter"].get("name"),
                "tier": pol["tier"], "action": pol["action"], "required_approvers": pol["required_approvers"],
                "total_affected": ic.get("total_affected"), "direct_callers": ic.get("ring_1"),
                "affected_files": pc.get("affected_files"), "affected_directories": pc.get("affected_directories"),
                "signature": d["signature"][:16] + "…"}

    def precedent(self, symbol: str) -> dict:
        imp, d, pol = self._impact_and_policy(symbol)
        if imp is None:
            return {"error": f"no symbol named {symbol} in the graph"}
        prec = self.led.precedent(target_symbols=[symbol], signature=d["signature"],
                                  target_fqns=[imp.epicenter_fqn] if imp.epicenter_fqn else None)
        contra = prec.get("contradiction") or {}
        return {"symbol": symbol, "approved": prec.get("approved", 0), "rejected": prec.get("rejected", 0),
                "has_identical_contradiction": prec.get("contradiction_strength") == "identical",
                "contradiction_actor": contra.get("actor"), "contradiction_change_id": contra.get("change_id"),
                "contradiction_rationale": (contra.get("rationale") or "")[:240] or None}

    def propose_reviewers(self, symbol: str) -> dict:
        imp, d, pol = self._impact_and_policy(symbol)
        if imp is None:
            return {"error": f"no symbol named {symbol} in the graph"}
        prior = []
        for r in self.led.rows():
            if symbol in (r.get("target_symbols") or []) and r.get("decision") == "approve" \
                    and not (r.get("seeded") or (r.get("extra") or {}).get("seeded")):
                a = r.get("actor")
                if a and a not in prior:
                    prior.append(a)
        return {"symbol": symbol, "prior_approvers": prior[:5],
                "required_owner": pol.get("required_owner"),
                "required_approvers": pol["required_approvers"],
                "note": "Quorum is per change; the change author cannot self-approve (four-eyes)."}

    def execute(self, name: str, args: dict) -> dict:
        fn = {"blast_radius": self.blast_radius, "precedent": self.precedent,
              "propose_reviewers": self.propose_reviewers}.get(name)
        if not fn:
            return {"error": f"unknown tool {name}"}
        sym = (args or {}).get("symbol")
        if not sym:
            return {"error": "missing required argument: symbol"}
        try:
            return fn(str(sym))
        except Exception as exc:  # never let a tool error crash the loop
            return {"error": f"tool {name} failed: {exc}"}


def _deterministic_plan(tools: ReviewTools, symbol: str) -> dict:
    """Fixed-order tool plan + template recommendation. Same tools, same facts, no model.
    Returned when no LLM key has quota so the assistant always works (labeled deterministic)."""
    steps = []
    br = tools.blast_radius(symbol)
    steps.append({"tool": "blast_radius", "args": {"symbol": symbol}, "result": br})
    if br.get("error"):
        return {"answer": br["error"], "steps": steps, "provider": None, "deterministic": True}
    pr = tools.precedent(symbol)
    steps.append({"tool": "precedent", "args": {"symbol": symbol}, "result": pr})
    rv = tools.propose_reviewers(symbol)
    steps.append({"tool": "propose_reviewers", "args": {"symbol": symbol}, "result": rv})

    sentences = [f"Changing {symbol} reaches {br['total_affected']} dependent definitions "
                 f"({br['direct_callers']} direct), placing it in the {br['tier']} tier "
                 f"({br['action']}, {br['required_approvers']} approver(s))."]
    if pr.get("has_identical_contradiction"):
        sentences.append(f"A prior reviewer ({pr.get('contradiction_actor')}) rejected this exact blast "
                         f"signature, so it is blocked until an accountable override.")
        nxt = "File an RFC or record an accountable override; do not approve on the identical signature alone."
    elif pr.get("rejected"):
        sentences.append("There is a prior rejection on this symbol worth reading before approving.")
        nxt = "Read the prior rejection, then get the required approvers."
    else:
        owner = rv.get("required_owner")
        nxt = (f"Pull in the owner ({owner}) and " if owner else "Get ") + \
              f"{br['required_approvers']} distinct approver(s); the author cannot self-approve."
    sentences.append("Recommended next step: " + nxt)
    return {"answer": " ".join(sentences), "steps": steps, "provider": None, "deterministic": True}


def run_agent(graph, ledger, symbol: str, question: Optional[str] = None, *,
              max_depth: int = 3, max_steps: int = MAX_STEPS, timeout: Optional[float] = None) -> dict:
    """Run the tool-using assistant. Returns {answer, steps, provider, deterministic}.

    Tries a real LLM tool-loop over the deterministic tools; falls back to a deterministic
    plan. `steps` is the visible reasoning trace (each tool call + its engine result) so a
    reviewer can audit exactly which facts the recommendation rests on."""
    import json as _json
    tools = ReviewTools(graph, ledger, max_depth=max_depth)
    q = (question or "").strip() or f"Should I approve the change to {symbol}? What should I do?"
    user = f"The reviewer is looking at the symbol `{symbol}`. {q}"
    messages = [{"role": "system", "content": _SYSTEM}, {"role": "user", "content": user}]
    steps = []

    for _ in range(max_steps):
        msg, provider = llm_mod.chat(messages, tools=TOOL_SCHEMAS, timeout=timeout)
        if msg is None:
            return _deterministic_plan(tools, symbol)            # no LLM available -> deterministic
        tool_calls = msg.get("tool_calls") or []
        if not tool_calls:
            answer = (msg.get("content") or "").strip()
            if answer:
                return {"answer": answer, "steps": steps, "provider": provider, "deterministic": False}
            break                                                 # empty, no tools -> fall back
        # record the assistant turn verbatim so the follow-up call has valid context
        messages.append({"role": "assistant", "content": msg.get("content") or "", "tool_calls": tool_calls})
        for tc in tool_calls:
            fn = (tc.get("function") or {})
            name = fn.get("name")
            try:
                args = _json.loads(fn.get("arguments") or "{}")
            except Exception:
                args = {}
            result = tools.execute(name, args)
            steps.append({"tool": name, "args": args, "result": result})
            messages.append({"role": "tool", "tool_call_id": tc.get("id") or name,
                             "name": name, "content": _json.dumps(result)})

    # ran out of steps (or empty answer) with facts gathered: deterministic compose, but keep
    # the real tool trace the model produced so the agentic work is still visible.
    plan = _deterministic_plan(tools, symbol)
    if steps:
        plan["steps"] = steps + plan["steps"]
        plan["note"] = "LLM gathered facts via tools; recommendation composed deterministically after step budget."
    return plan
