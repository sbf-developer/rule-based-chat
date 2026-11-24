"""Local window for the existing Rules-Based Chat assistant."""

import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText

from app import MAX_INPUT, Session, respond


root = tk.Tk()
root.title("Rule-Based Chat")
root.geometry("680x460")
root.minsize(420, 260)
root.columnconfigure(0, weight=1)
root.rowconfigure(0, weight=1)
session = Session()

transcript = ScrolledText(root, wrap="word", state="disabled", padx=12, pady=12)
transcript.grid(row=0, column=0, columnspan=2, sticky="nsew", padx=12, pady=12)


def append(text):
    transcript.configure(state="normal")
    transcript.insert("end", text.replace("\x00", "\\x00") + "\n\n")
    transcript.configure(state="disabled")
    transcript.see("end")


def send(event=None):
    message = entry.get()
    entry.delete(0, "end")
    if not message.strip():
        return
    shown = message if len(message) <= MAX_INPUT else message[:100] + "…"
    append(f"You: {shown}")
    reply = respond(message, session)
    if reply.exit:
        root.destroy()
        return
    append(f"Chat: {reply.text}")
    entry.focus_set()


entry = ttk.Entry(root)
entry.grid(row=1, column=0, sticky="ew", padx=(12, 6), pady=(0, 12))
entry.bind("<Return>", send)
ttk.Button(root, text="Send", command=send).grid(row=1, column=1, padx=(0, 12), pady=(0, 12))
append("Type a message to start. Use /help for examples.")
entry.focus_set()
root.mainloop()
