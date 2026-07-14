import os
import json
import httpx
from cryptography.fernet import Fernet
from sqlalchemy.orm import Session
from models import AppSetting

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

_fernet = Fernet(os.environ["FERNET_KEY"].encode("utf-8"))


def encrypt_value(value: str) -> str:
    return _fernet.encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_value(value: str) -> str:
    return _fernet.decrypt(value.encode("utf-8")).decode("utf-8")


def get_setting(db: Session, key: str):
    row = db.query(AppSetting).filter(AppSetting.key == key).first()
    return row.value if row else None


def set_setting(db: Session, key: str, value: str):
    row = db.query(AppSetting).filter(AppSetting.key == key).first()
    if row:
        row.value = value
    else:
        db.add(AppSetting(key=key, value=value))
    db.commit()


def get_openrouter_key(db: Session):
    enc = get_setting(db, "openrouter_api_key")
    if enc:
        try:
            return decrypt_value(enc)
        except Exception:
            return None
    return os.environ.get("OPENROUTER_API_KEY")


def get_model(db: Session):
    return get_setting(db, "openrouter_model") or os.environ.get(
        "OPENROUTER_MODEL", "deepseek/deepseek-chat-v3-0324:free"
    )


SYSTEM_PROMPT = """You are the AI assistant embedded in the wespeak.ai CRM (an AI consulting company).
You convert a user's free-form command into a single structured JSON object that the CRM backend executes.

Respond with ONLY valid JSON (no markdown, no code fences). Schema:
{
  "action": one of ["create_contact","create_company","create_deal","create_project","create_activity","summarize","answer","search"],
  "data": { ... fields relevant to the action ... },
  "message": "a short friendly confirmation or answer in the same language as the user's command"
}

Field guidance:
- create_contact: {first_name, last_name, email, phone, title, status(one of lead/prospect/customer/inactive)}
- create_company: {name, industry, website, phone, email}
- create_deal: {title, value(number), currency, stage(one of lead/qualified/proposal/negotiation/won/lost)}
- create_project: {name, description, status(one of planning/active/on_hold/completed/cancelled), priority(low/medium/high)}
- create_activity: {type(call/email/meeting/task/note), subject, description}
- summarize / answer / search: leave data empty, put the useful text in "message".

Detect the language (English or Hungarian) from the user's command and reply in that language.
If the command is ambiguous, choose action "answer" and ask for clarification in "message"."""


async def run_ai_command(api_key: str, model: str, command: str, context: str = "") -> dict:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
    ]
    if context:
        messages.append({"role": "system", "content": f"Current CRM context:\n{context}"})
    messages.append({"role": "user", "content": command})

    body = {
        "model": model,
        "messages": messages,
        "temperature": 0.3,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": os.environ.get("FRONTEND_URL", "https://wespeak.ai"),
        "X-Title": "wespeak.ai CRM",
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(OPENROUTER_URL, headers=headers, json=body)

    if resp.status_code != 200:
        raise RuntimeError(f"OpenRouter error ({resp.status_code}): {resp.text}")

    data = resp.json()
    content = data["choices"][0]["message"]["content"].strip()

    # Strip code fences if present
    if content.startswith("```"):
        content = content.strip("`")
        if content.lower().startswith("json"):
            content = content[4:]
        content = content.strip()

    try:
        parsed = json.loads(content)
    except Exception:
        parsed = {"action": "answer", "data": {}, "message": content}

    if "action" not in parsed:
        parsed["action"] = "answer"
    if "data" not in parsed:
        parsed["data"] = {}
    if "message" not in parsed:
        parsed["message"] = ""
    return parsed
