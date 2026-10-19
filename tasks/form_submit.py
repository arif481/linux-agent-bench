import json

from lab.task import APPS, Check, Task

EXPECTED = {"name": "Priya Das", "email": "priya@example.com", "subscribe": False}


def setup(env):
    env.launch_python(APPS / "form_app.py", "--out", env.work / "form.json", wait_title="^Registration$")


def check(env):
    out = env.work / "form.json"
    if not out.exists():
        return Check(success=False, details="form was never submitted")
    data = json.loads(out.read_text())
    got = {"name": data.get("name", "").strip(), "email": data.get("email", "").strip(),
           "subscribe": data.get("subscribe")}
    return Check(success=got == EXPECTED, details=f"submitted: {got}")


def oracle(env):
    env.cu("focus", "^Registration$")
    env.cu("type", "Priya Das", "--into", "^Registration$")
    env.cu("key", "Tab", "--into", "^Registration$")
    env.cu("type", "priya@example.com", "--into", "^Registration$")
    env.cu("key", "Tab", "Tab", "space", "--into", "^Registration$")  # skip the checkbox, press Submit


TASK = Task(
    id="form-submit",
    instruction="Fill in the Registration form with the name Priya Das and the email "
                "priya@example.com. Leave the newsletter box unticked, then submit the form.",
    setup=setup, check=check, oracle=oracle, tags=("tk", "forms"),
)
