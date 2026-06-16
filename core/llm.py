"""Optional LLM assist layer - REAL AI, kept strictly off the trust path.

What it does: turns the engine's already-computed governance facts (blast radius,
precedent, tier, action) into a short natural-language reviewer brief, and powers a
question-answering assistant whose TOOLS are the deterministic engine. What it never
does: produce a number, compute a blast radius, or decide a verdict. Every figure is
passed IN from core/impact.py; the model only explains and proposes. The verdict
stays human; the audit ledger stays deterministic and tamper-evident.

Resilience: a free provider ladder (Cerebras -> Groq -> OpenRouter -> Gemini),
OpenAI-compatible, each behind a hard timeout. If no key has quota, generate()
returns (None, None) and the caller falls back to a deterministic template, so the
product is fully functional with zero keys (the brief is then labeled deterministic).

Standard library only (urllib). Keys are read from the environment or a local .env
(never logged, never returned to the client).
"""
from __future__ import annotations

import json
import os
import urllib.request
from typing import Optional, Tuple

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None

_TIMEOUT = float(os.environ.get("KEYSTONE_LLM_TIMEOUT", "9"))

_ENV_LOADED = False


def _load_dotenv():
    """Best-effort load of repo-root .env so keys placed there are usable in dev,
    without adding a python-dotenv dependency. Existing env vars win."""
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    _ENV_LOADED = True
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env")
    try:
        with open(os.path.abspath(path), encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())
    except Exception:
        pass


_OR_URL = "https://openrouter.ai/api/v1/chat/completions"

# (name, base_url, key_env, model_env, default_model)
# Several OpenRouter free models are listed because each carries its OWN upstream
# rate limit, so a 429 on one tool-calling model falls through to the next that is
# genuinely good at tool use - the assistant degrades to the deterministic plan only
# when ALL are exhausted. Order: fast/cheap first, strong tool-callers as fallbacks.
_PROVIDERS = [
    ("cerebras", "https://api.cerebras.ai/v1/chat/completions", "CEREBRAS_API_KEY", "CEREBRAS_MODEL", "gpt-oss-120b"),
    ("groq", "https://api.groq.com/openai/v1/chat/completions", "GROQ_API_KEY", "GROQ_MODEL", "llama-3.3-70b-versatile"),
    ("openrouter", _OR_URL, "OPENROUTER_API_KEY", "OPENROUTER_MODEL", "google/gemma-4-31b-it:free"),
    ("openrouter", _OR_URL, "OPENROUTER_API_KEY", "OPENROUTER_MODEL_2", "meta-llama/llama-3.3-70b-instruct:free"),
    ("openrouter", _OR_URL, "OPENROUTER_API_KEY", "OPENROUTER_MODEL_3", "qwen/qwen-2.5-72b-instruct:free"),
    ("gemini", "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions", "GEMINI_API_KEY", "GEMINI_MODEL", "gemini-3.5-flash"),
]


def _get_gemini_tools() -> list[types.Tool]:
    if not genai:
        return []
    return [
        types.Tool(function_declarations=[
            types.FunctionDeclaration(
                name="blast_radius",
                description="Deterministic blast radius and governance tier for a symbol from the Orbit code graph.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "symbol": types.Schema(
                            type=types.Type.STRING,
                            description="the symbol/definition name to analyze"
                        )
                    },
                    required=["symbol"]
                )
            ),
            types.FunctionDeclaration(
                name="precedent",
                description="Prior governed decisions on a symbol: approvals, rejections, and any signature-identical contradiction.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "symbol": types.Schema(
                            type=types.Type.STRING,
                            description="the symbol/definition name to check precedent for"
                        )
                    },
                    required=["symbol"]
                )
            ),
            types.FunctionDeclaration(
                name="propose_reviewers",
                description="Suggested reviewers for a symbol: who approved it before and the policy-required owner.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "symbol": types.Schema(
                            type=types.Type.STRING,
                            description="the symbol/definition name to propose reviewers for"
                        )
                    },
                    required=["symbol"]
                )
            )
        ])
    ]


def _convert_messages_to_gemini(messages: list) -> Tuple[Optional[str], list]:
    if not genai:
        return None, []
    import json as _json
    system_instruction = None
    contents = []
    
    for msg in messages:
        role = msg.get("role")
        content = msg.get("content") or ""
        
        if role == "system":
            system_instruction = content
            continue
            
        parts = []
        
        if role == "user":
            parts.append(types.Part.from_text(text=content))
            contents.append(types.Content(role="user", parts=parts))
            
        elif role == "assistant":
            if content:
                parts.append(types.Part.from_text(text=content))
            
            tool_calls = msg.get("tool_calls") or []
            for tc in tool_calls:
                fn = tc.get("function") or {}
                try:
                    args = _json.loads(fn.get("arguments") or "{}")
                except Exception:
                    args = {}
                parts.append(types.Part.from_function_call(
                    name=fn.get("name"),
                    args=args
                ))
            contents.append(types.Content(role="model", parts=parts))
            
        elif role == "tool":
            try:
                result = _json.loads(content)
            except Exception:
                result = {"result": content}
            
            parts.append(types.Part.from_function_response(
                name=msg.get("name"),
                response=result,
                id=msg.get("tool_call_id")
            ))
            contents.append(types.Content(role="tool", parts=parts))
            
    return system_instruction, contents


def _call_gemini_sdk_generate(prompt: str, system: str, max_tokens: int, timeout: float) -> Optional[str]:
    if not genai:
        return None
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        return None
    model = os.environ.get("GEMINI_MODEL") or "gemini-3.5-flash"
    try:
        client = genai.Client(api_key=key)
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system,
                max_output_tokens=max_tokens,
                temperature=0.2
            )
        )
        if response.text:
            return response.text.strip()
    except Exception:
        pass
    return None


def _call_gemini_sdk_chat(messages: list, tools: Optional[list], max_tokens: int) -> Optional[dict]:
    if not genai:
        return None
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        return None
    model = os.environ.get("GEMINI_MODEL") or "gemini-3.5-flash"
    try:
        system_instruction, contents = _convert_messages_to_gemini(messages)
        
        config_args = {
            "max_output_tokens": max_tokens,
            "temperature": 0.2
        }
        if system_instruction:
            config_args["system_instruction"] = system_instruction
        if tools:
            config_args["tools"] = _get_gemini_tools()
            
        client = genai.Client(api_key=key)
        response = client.models.generate_content(
            model=model,
            contents=contents,
            config=types.GenerateContentConfig(**config_args)
        )
        
        translated = {"content": response.text or ""}
        
        tool_calls = []
        if response.function_calls:
            for call in response.function_calls:
                cid = getattr(call, "id", None) or call.name
                tool_calls.append({
                    "id": cid,
                    "type": "function",
                    "function": {
                        "name": call.name,
                        "arguments": json.dumps(call.args)
                    }
                })
        if tool_calls:
            translated["tool_calls"] = tool_calls
            
        return translated
    except Exception:
        pass
    return None


def available_providers() -> list:
    """Distinct provider names that have a key configured (never the key values).
    Deduped so multiple models behind one provider (e.g. OpenRouter) list once."""
    _load_dotenv()
    seen, out = set(), []
    if os.environ.get("GEMINI_API_KEY"):
        seen.add("gemini-sdk")
        out.append("gemini-sdk")
    for (name, _u, ke, _me, _dm) in _PROVIDERS:
        if os.environ.get(ke) and name not in seen:
            seen.add(name)
            out.append(name)
    return out



def _call(url: str, key: str, model: str, system: str, prompt: str, max_tokens: int, timeout: float) -> Optional[str]:
    body = json.dumps({
        "model": model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        "max_tokens": max_tokens, "temperature": 0.2,
    }).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST",
                                 headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        d = json.loads(r.read().decode("utf-8"))
    msg = (d.get("choices") or [{}])[0].get("message", {})
    text = (msg.get("content") or "").strip()
    return text or None


def _call_chat(url: str, key: str, model: str, messages: list, tools: Optional[list],
               max_tokens: int, timeout: float) -> Optional[dict]:
    """One OpenAI-compatible chat completion that MAY return tool_calls. Returns the
    raw assistant message dict ({content, tool_calls?}) or None. Used by the agent
    loop (core/agent.py) to let the model drive the deterministic engine tools."""
    payload = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": 0.2}
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST",
                                 headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        d = json.loads(r.read().decode("utf-8"))
    return (d.get("choices") or [{}])[0].get("message") or None


def chat(messages: list, *, tools: Optional[list] = None, max_tokens: int = 380,
         timeout: Optional[float] = None) -> Tuple[Optional[dict], Optional[str]]:
    """Provider-ladder chat with optional tool-calling. Returns (assistant_message, provider)
    or (None, None). Never raises. The assistant_message is the raw OpenAI-compatible dict so
    the caller can read either .content (final answer) or .tool_calls (a step in the loop)."""
    if os.environ.get("KEYSTONE_LLM_DISABLED"):
        return None, None
    _load_dotenv()
    if os.environ.get("GEMINI_API_KEY"):
        res = _call_gemini_sdk_chat(messages, tools, max_tokens)
        if res is not None:
            return res, "gemini-sdk"
    t = timeout if timeout is not None else _TIMEOUT
    for (name, url, key_env, model_env, default_model) in _PROVIDERS:
        key = os.environ.get(key_env)
        if not key:
            continue
        model = os.environ.get(model_env) or default_model
        try:
            msg = _call_chat(url, key, model, messages, tools, max_tokens, t)
            if msg is not None:
                return msg, name
        except Exception:
            continue   # provider lacks tool support / dead key / quota -> next, then deterministic
    return None, None


def generate(prompt: str, *, system: str = "You are Keystone's review assistant.",
             max_tokens: int = 320, timeout: Optional[float] = None) -> Tuple[Optional[str], Optional[str]]:
    """Try the provider ladder; return (text, provider_name) or (None, None).
    Never raises. The caller MUST treat the text as advisory prose, never as a
    number or a verdict."""
    if os.environ.get("KEYSTONE_LLM_DISABLED"):
        return None, None                       # offline / tests / CI: deterministic only, no network
    _load_dotenv()
    if os.environ.get("GEMINI_API_KEY"):
        res = _call_gemini_sdk_generate(prompt, system, max_tokens, timeout or _TIMEOUT)
        if res:
            return res, "gemini-sdk"
    t = timeout if timeout is not None else _TIMEOUT
    for (name, url, key_env, model_env, default_model) in _PROVIDERS:
        key = os.environ.get(key_env)
        if not key:
            continue
        model = os.environ.get(model_env) or default_model
        try:
            text = _call(url, key, model, system, prompt, max_tokens, t)
            if text:
                return text, name
        except Exception:
            continue   # dead key / quota / timeout -> next provider, then deterministic fallback
    return None, None


_BRIEF_SYSTEM = (
    "You are Keystone's governed-review assistant. You help a human reviewer by explaining "
    "governance FACTS that were already computed deterministically from a code knowledge graph. "
    "Hard rules: never invent or restate a number or a name that is not in the facts; never state "
    "a verdict as a decision (the human decides); output 2 to 4 plain sentences, no markdown, no lists."
)


def _facts_block(ctx: dict) -> str:
    c = ctx.get("counts", {})
    prec = ctx.get("precedent", {}) or {}
    contra = prec.get("contradiction") or {}
    lines = [
        f"symbol: {ctx.get('symbol')} ({ctx.get('fqn') or ctx.get('file') or ''})",
        f"blast radius: {c.get('affected_definitions', 0)} dependent definitions across "
        f"{c.get('affected_files', 0)} files / {c.get('affected_directories', 0)} directories",
        f"policy tier: {ctx.get('tier')}; action: {ctx.get('action')}; required approvers: {ctx.get('required_approvers')}",
        f"precedent: {prec.get('approved', 0)} prior approvals, {prec.get('rejected', 0)} prior rejections",
    ]
    if contra:
        lines.append(f"contradiction: {contra.get('actor')} rejected {contra.get('change_id')} on the same blast "
                     f"signature, saying: \"{(contra.get('rationale') or '')[:200]}\"")
    return "\n".join(lines)


def _deterministic_brief(ctx: dict) -> str:
    c = ctx.get("counts", {})
    prec = ctx.get("precedent", {}) or {}
    contra = prec.get("contradiction") or {}
    parts = [f"Changing {ctx.get('symbol')} reaches {c.get('affected_definitions', 0)} dependent definitions across "
             f"{c.get('affected_files', 0)} files, placing it in the {ctx.get('tier')} tier "
             f"({ctx.get('action')}, {ctx.get('required_approvers')} approver(s) required)."]
    if contra and prec.get("contradiction_strength") == "identical":
        parts.append(f"A prior identical-blast rejection by {contra.get('actor')} ({contra.get('change_id')}) is on "
                     f"record, so this is blocked until an accountable override.")
    elif prec.get("rejected"):
        parts.append("There is a prior rejection on this symbol worth reading before approving.")
    else:
        parts.append("No contradicting precedent is on record for this exact blast radius.")
    return " ".join(parts)


def review_brief(ctx: dict, *, timeout: Optional[float] = None) -> dict:
    """Return {brief, provider, deterministic}. Tries a real LLM over the engine
    facts; falls back to a deterministic template so it always works."""
    prompt = ("Write a short reviewer brief from these facts. Explain the risk in one or two sentences "
              "and recommend a concrete next step (approve with reason / get a second approver / file an "
              "RFC / override with accountability). Use only these facts:\n\n" + _facts_block(ctx))
    text, provider = generate(prompt, system=_BRIEF_SYSTEM, max_tokens=260, timeout=timeout)
    if text:
        return {"brief": text, "provider": provider, "deterministic": False}
    return {"brief": _deterministic_brief(ctx), "provider": None, "deterministic": True}

