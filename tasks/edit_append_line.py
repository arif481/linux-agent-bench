from lab.task import Check, Task

INITIAL = "Shopping list\n- milk\n- bread\n"
EXPECTED = ["Shopping list", "- milk", "- bread", "- eggs"]


def setup(env):
    (env.work / "notes.txt").write_text(INITIAL)
    env.launch(["gedit", "--new-window", str(env.work / "notes.txt")], wait_title="notes.txt")


def check(env):
    text = (env.work / "notes.txt").read_text()
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return Check(success=lines == EXPECTED, details=f"file now: {lines}")


def oracle(env):
    env.cu("focus", "notes.txt")
    env.cu("key", "ctrl+End", "--into", "notes.txt")
    env.cu("key", "Return", "--into", "notes.txt")
    env.cu("type", "- eggs", "--into", "notes.txt")
    env.cu("key", "ctrl+s", "--into", "notes.txt")


TASK = Task(
    id="edit-append-line",
    instruction="A text editor is open with notes.txt. Add a new line '- eggs' at the end of the "
                "shopping list and save the file.",
    setup=setup, check=check, oracle=oracle, tags=("gedit", "editing"),
)
