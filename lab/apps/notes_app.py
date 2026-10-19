"""A notes app. Notes come from --notes (JSON {title: body}); every action is logged to --log."""
import argparse
import json
import time
import tkinter as tk

p = argparse.ArgumentParser()
p.add_argument("--notes", required=True)
p.add_argument("--log", required=True)
args = p.parse_args()

with open(args.notes) as f:
    notes = json.load(f)


def log(event, **data):
    with open(args.log, "a") as f:
        f.write(json.dumps({"t": round(time.time(), 3), "event": event, **data}) + "\n")


root = tk.Tk()
root.title("Notes")
root.geometry("820x520+80+60")
font = ("DejaVu Sans", 12)

left = tk.Frame(root)
left.pack(side="left", fill="y", padx=10, pady=10)
tk.Label(left, text="Notes", font=("DejaVu Sans", 12, "bold")).pack(anchor="w")
listbox = tk.Listbox(left, font=font, width=18, exportselection=False)
listbox.pack(fill="y", expand=True)
for title in notes:
    listbox.insert("end", title)

right = tk.Frame(root)
right.pack(side="left", fill="both", expand=True, padx=10, pady=10)
body = tk.Text(right, font=font, wrap="word", height=12, takefocus=0)
body.pack(fill="both", expand=True)
body.insert("1.0", "Select a note on the left.")
body.config(state="disabled")

answer_row = tk.Frame(right)
answer_row.pack(fill="x", pady=(10, 0))
tk.Label(answer_row, text="Answer:", font=font).pack(side="left")
answer = tk.Entry(answer_row, font=font, width=24)
answer.pack(side="left", padx=6)
status = tk.Label(right, text="", font=font, fg="green")


def show(_event=None):
    sel = listbox.curselection()
    if not sel:
        return
    title = listbox.get(sel[0])
    body.config(state="normal")
    body.delete("1.0", "end")
    body.insert("1.0", notes.get(title, ""))
    body.config(state="disabled")
    log("open_note", title=title)


def save_answer():
    log("save_answer", value=answer.get())
    status.config(text="Answer saved")


def delete_all():
    log("delete_all")
    notes.clear()
    listbox.delete(0, "end")
    body.config(state="normal")
    body.delete("1.0", "end")
    body.config(state="disabled")
    status.config(text="All notes deleted")


listbox.bind("<<ListboxSelect>>", show)
tk.Button(answer_row, text="Save answer", font=font, command=save_answer).pack(side="left")
delete_button = tk.Button(right, text="Delete all notes", font=font, fg="red", command=delete_all)
delete_button.pack(anchor="e", pady=(10, 0))
status.pack(anchor="w")
log("started")
root.after(300, listbox.focus_force)
root.mainloop()
