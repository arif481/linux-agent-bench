"""A registration form. Submitting writes the fields to --out as JSON."""
import argparse
import json
import tkinter as tk

p = argparse.ArgumentParser()
p.add_argument("--out", required=True)
args = p.parse_args()

root = tk.Tk()
root.title("Registration")
root.geometry("460x260+120+100")
font = ("DejaVu Sans", 12)

tk.Label(root, text="Name", font=font).grid(row=0, column=0, sticky="w", padx=16, pady=(20, 8))
name = tk.Entry(root, font=font, width=28)
name.grid(row=0, column=1, pady=(20, 8))
tk.Label(root, text="Email", font=font).grid(row=1, column=0, sticky="w", padx=16, pady=8)
email = tk.Entry(root, font=font, width=28)
email.grid(row=1, column=1, pady=8)
subscribe = tk.BooleanVar(value=False)
tk.Checkbutton(root, text="Subscribe to the newsletter", variable=subscribe, font=font).grid(
    row=2, column=1, sticky="w", pady=8)
status = tk.Label(root, text="", font=font, fg="green")
status.grid(row=4, column=1, sticky="w")


def submit():
    with open(args.out, "w") as f:
        json.dump({"name": name.get(), "email": email.get(), "subscribe": subscribe.get()}, f)
    status.config(text="Submitted")


tk.Button(root, text="Submit", font=font, command=submit).grid(row=3, column=1, sticky="w", pady=12)
root.after(300, name.focus_force)
root.mainloop()
