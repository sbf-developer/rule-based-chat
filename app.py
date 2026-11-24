"""A deterministic English-language chat assistant. Run with Python 3.10+."""

from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass, field
from datetime import datetime
from difflib import get_close_matches
import math
import operator
import re
import sys
import unicodedata
from collections.abc import Callable


MAX_INPUT = 4000
MAX_EXPRESSION = 256
MAX_NUMBER = 10**100
MAX_MEMORIES = 32
NUMBER = r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:e[+-]?[0-9]+)?"
WORD = re.compile(r"[^\W_]+(?:['’\-][^\W_]+)*", re.UNICODE)
ENDING = re.compile(r"[?.!]+$")
SUPERSCRIPT = re.compile(r"(?<=[0-9)])([⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻]+)")
SUPERSCRIPT_DIGITS = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻", "0123456789+-")
GREETING_PREFIX = re.compile(
    r"(?:hi|hello|hey|good morning|good afternoon|good evening)(?: there)?"
    r"(?:[,!]\s*(?=\S)|\s+(?=(?:how|what|could|can|would|please|tell|explain|calculate)\b))",
    re.I,
)
REQUEST_PREFIX = re.compile(r"(?:please |(?:can|could|would|will) you (?:please )?)", re.I)
CONVERSATION_PREFIX = re.compile(
    r"(?:(?:not much|nothing much|good thanks|yeah|yep|ok(?:ay)?|alright|sure|well|anyway)"
    r"(?:[,;.!]\s*|\s+)(?=\S)|"
    r"(?:i (?:(?:was|am) )?|i['’]m )(?:just )?(?:wonder(?:ing)?|curious)(?: (?:about|if))?,?\s+|"
    r"(?:quick question|one more thing)[:,]\s*)",
    re.I,
)
MATH_REQUEST = re.compile(
    r"^(?:calculate|compute|evaluate|solve|work out|figure out|"
    r"(?:what is|what's)(?: the (?:answer|result|value) (?:of|to))?|"
    r"how much (?:is|does)|what do you get (?:if|when) you)\b\s*"
)
QUESTION = re.compile(
    r"(?:what is|what's|what are|tell me about|explain|define|describe|"
    r"i (?:want|would like) to (?:learn|know) about|"
    r"(?:give me )?(?:a |an )?(?:(?:quick|short|simple) )?(?:overview|rundown|explanation) (?:of|on)) (.+)"
)
STATUS = re.compile(
    r"(?:how (?:are you(?: (?:doing|feeling))?|are things(?: with you)?|"
    r"have you been|(?:is|are) (?:it|things) going)(?: (?:today|lately|these days))?"
    r"|how'?s (?:it going|your day(?: going)?|everything(?: going)?)"
    r"|what'?s up(?: with you)?|how (?:about you|r u|are u|you doing)(?: today)?"
    r"|how're you(?: doing)?|how've (?:you|things) been|hru|hbu|wbu|and you"
    r"|(?:(?:yo|you|hey) )?(?:wass+up|wazz+up|whass+up|w(?:hat)?sup|sup)(?: with you)?)"
)
SMALL_TALK_LEAD = re.compile(
    r"(?:not much|nothing much|nothing new|pretty good|doing (?:good|well|fine)|"
    r"i'?m (?:good|fine|okay|well)|good thanks|good|okay|fine)(?:[,!.;]+\s*|\s+)"
)

HELP = """Try one of these:
  Calculate (12 + 8) / 4, then ask: then multiply by 3
  What is 15% of 240?
  Convert 72 F to C, or: 5 miles in km
  Explain recursion
  Summarize: Paste a few sentences here.
  Word count: Paste any text here.
  Uppercase: hello world, then ask: make it lowercase
  Draft an email about moving the meeting
  Help me plan a weekend trip
  Remember that my favorite color is blue, then ask: what's my favorite color?
  /memory lists saved notes. /reset clears this session. /quit exits."""

TOPICS = {
    "algorithm": "An algorithm is a sequence of steps for solving a problem. Sorting a list from smallest to largest is a common example.",
    "api": "An API is a defined way for one program to interact with another. It describes what you can request and what to expect back.",
    "binary": "Binary is a base-two number system. Its digits are 0 and 1. The binary number 101 represents 5 in decimal.",
    "database": "A database is an organized collection of data. A database management system lets programs store, query, and update it.",
    "gravity": "Gravity is the interaction that keeps planets in orbit and pulls falling objects toward Earth.",
    "html": "HTML describes the structure of web content. Elements identify things such as headings, paragraphs, and links.",
    "llm": "A large language model learns patterns from training data and uses them to predict tokens in context.",
    "photosynthesis": "Photosynthesis uses energy from light to make sugars. Plants use carbon dioxide and water in the process and release oxygen.",
    "python": "Python is a general-purpose programming language used for tasks such as scripting, data analysis, and web development.",
    "recursion": "Recursion solves a problem by calling the same function on a smaller case. A base case tells it when to stop.",
    "rule-based chatbot": "A rule-based chatbot chooses replies using predefined rules, such as matching phrases, running a calculation, or looking up a saved note.",
    "variable": "A variable is a name used to refer to a value. For example, after `score = 10` in Python, `score` refers to the integer 10.",
}
TOPIC_ALIASES = {
    "apis": "api", "algorithms": "algorithm", "databases": "database",
    "large language models": "llm", "large language model": "llm", "llms": "llm",
    "python programming": "python", "rule based chatbot": "rule-based chatbot",
    "variables": "variable",
}
PLACE_LOCATIONS = {
    "amsterdam": "Amsterdam is in the Netherlands.",
    "athens": "Athens is in Greece.",
    "berlin": "Berlin is in Germany.",
    "beijing": "Beijing is in northern China.",
    "cairo": "Cairo is in Egypt, on the Nile.",
    "copenhagen": "Copenhagen is in Denmark, on the east coast of Zealand and partly on Amager.",
    "london": "London is in southeastern England, in the United Kingdom.",
    "madrid": "Madrid is in central Spain.",
    "new york city": "New York City is in New York State, on the east coast of the United States.",
    "oslo": "Oslo is in Norway, at the northern end of the Oslofjord.",
    "paris": "Paris is in northern France, on the Seine. It's the capital of France.",
    "paris texas": "Paris, Texas, is in northeastern Texas, in the United States.",
    "rome": "Rome is in central Italy.",
    "stockholm": "Stockholm is in eastern Sweden, where Lake Mälaren meets the Baltic Sea.",
    "sydney": "Sydney is in New South Wales, on the east coast of Australia.",
    "tokyo": "Tokyo is in Japan, on the east coast of Honshu.",
    "toronto": "Toronto is in Ontario, Canada, on the shore of Lake Ontario.",
}
AMBIGUOUS_PLACES = {"cambridge", "new york", "springfield", "washington"}
PLACE_ALIASES = {"paris france": "paris", "london uk": "london", "nyc": "new york city"}

OPERATORS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod, ast.Pow: operator.pow,
}
WORD_OPERATORS = {
    "to the power of": "**", "multiplied by": "*", "divided by": "/",
    "modulo": "%", "plus": "+", "minus": "-", "times": "*",
}
FOLLOW_OPERATORS = {"add": "+", "subtract": "-", "multiply": "*", "divide": "/"}

# Each factor converts a unit to meters, grams, or seconds for its group.
UNIT_GROUPS = {
    "length": {
        "mm": (0.001, "millimeter millimeters millimetre millimetres"),
        "cm": (0.01, "centimeter centimeters centimetre centimetres"),
        "m": (1, "meter meters metre metres"),
        "km": (1000, "kilometer kilometers kilometre kilometres"),
        "in": (0.0254, "inch inches"), "ft": (0.3048, "foot feet"),
        "yd": (0.9144, "yard yards"), "mi": (1609.344, "mile miles"),
    },
    "mass": {
        "mg": (0.001, "milligram milligrams"), "g": (1, "gram grams"),
        "kg": (1000, "kilogram kilograms"), "oz": (28.349523125, "ounce ounces"),
        "lb": (453.59237, "lbs pound pounds"),
    },
    "time": {
        "ms": (0.001, "millisecond milliseconds"), "s": (1, "sec second seconds"),
        "min": (60, "minute minutes"), "h": (3600, "hr hrs hour hours"),
        "d": (86400, "day days"),
    },
    "temperature": {
        "°C": (1, "c °c celsius"), "°F": (1, "f °f fahrenheit"),
        "K": (1, "k kelvin kelvins"),
    },
}
UNITS = {
    alias: (group, unit, factor)
    for group, entries in UNIT_GROUPS.items()
    for unit, (factor, aliases) in entries.items()
    for alias in {unit.lower(), *aliases.split()}
}


@dataclass(frozen=True)
class Reply:
    rule: str
    text: str
    exit: bool = False


@dataclass
class Session:
    notes: dict[str, str] = field(default_factory=dict)
    last_number: int | float | None = None
    last_text: str | None = None
    unmatched: int = 0
    suggested_topic: str | None = None
    last_place: str | None = None


def canonical(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).replace("’", "'")
    return " ".join(text.casefold().split())


def unwrap_prompt(prompt: str) -> str:
    while lead := CONVERSATION_PREFIX.match(prompt):
        remainder = REQUEST_PREFIX.sub("", prompt[lead.end():], count=1)
        if not remainder or remainder.startswith("/"):
            break
        prompt = remainder
    return prompt


def bounded_number(value: int | float) -> int | float:
    if type(value) not in (int, float) or not -MAX_NUMBER <= value <= MAX_NUMBER:
        raise ValueError("I only handle real numbers between −10^100 and 10^100.")
    return value


def format_number(value: int | float) -> str:
    if isinstance(value, int):
        return str(value)
    return "0" if value == 0 else format(value, ".12g")


def evaluate(node: ast.AST) -> int | float:
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        return bounded_number(node.value)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        value = evaluate(node.operand)
        return -value if isinstance(node.op, ast.USub) else value
    if isinstance(node, ast.BinOp) and type(node.op) in OPERATORS:
        left, right = evaluate(node.left), evaluate(node.right)
        if isinstance(node.op, ast.Pow) and abs(right) > 100:
            raise ValueError("Keep the exponent between −100 and 100.")
        return bounded_number(OPERATORS[type(node.op)](left, right))
    raise ValueError("Use numbers, arithmetic operators, and parentheses.")


def math_expression(text: str) -> str:
    text = text.replace("×", "*").replace("÷", "/").replace("−", "-").replace("^", "**")
    for phrase, symbol in WORD_OPERATORS.items():
        text = re.sub(rf"\b{phrase}\b", symbol, text)
    return re.sub(r"(?<=[0-9)])\s*x\s*(?=[0-9(])", "*", text).strip()


def math_reply(expression: str, session: Session) -> Reply:
    if len(expression) > MAX_EXPRESSION:
        return Reply("math", f"Keep calculations to {MAX_EXPRESSION} characters or fewer.")
    if not expression or not re.fullmatch(r"[0-9e. +*/%()\-]+", expression):
        return Reply("math", "Use numbers, arithmetic operators, and parentheses. Example: calculate (12 + 8) / 4.")
    try:
        result = evaluate(ast.parse(expression, mode="eval").body)
    except SyntaxError:
        return Reply("math", "I couldn't read that expression. Check the operators and parentheses.")
    except ZeroDivisionError:
        return Reply("math", "Division by zero is undefined.")
    except (OverflowError, RecursionError):
        return Reply("math", "That calculation exceeds my numeric limits.")
    except ValueError as error:
        return Reply("math", str(error))
    session.last_number = result
    return Reply("math", format_number(result))


def convert(value: str, source: str, target: str) -> Reply:
    if source not in UNITS or target not in UNITS:
        return Reply("conversion", "Supported conversions cover length, mass, time, and temperature. Try: 5 miles in km.")
    source_group, source_unit, source_factor = UNITS[source]
    target_group, target_unit, target_factor = UNITS[target]
    if source_group != target_group:
        return Reply("conversion", f"I can't convert {source_group} units into {target_group} units.")
    try:
        amount = bounded_number(float(value))
        if source_group == "temperature":
            minimum = {"°C": -273.15, "°F": -459.67, "K": 0}
            if amount < minimum[source_unit]:
                return Reply("conversion", "That temperature is below absolute zero.")
            kelvin = (amount - minimum[source_unit]) / (1.8 if source_unit == "°F" else 1)
            result = kelvin * (1.8 if target_unit == "°F" else 1) + minimum[target_unit]
        else:
            result = amount * (source_factor / target_factor)
        result = amount if source_unit == target_unit else bounded_number(result)
    except ValueError as error:
        return Reply("conversion", str(error))
    return Reply("conversion", f"{format_number(amount)} {source_unit} = {format_number(result)} {target_unit}")


def summarize(text: str) -> str:
    """Select representative sentences and retain their original order."""
    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+|\n+", text) if part.strip()]
    if len(sentences) <= 2:
        return text
    stop_words = set("a an and are as at be by for from has have i in is it of on or that the this to was were will with you".split())
    vocabulary = [set(WORD.findall(canonical(sentence))) - stop_words for sentence in sentences]
    frequency: dict[str, int] = {}
    for terms in vocabulary:
        for term in terms:
            frequency[term] = frequency.get(term, 0) + 1
    scores = [sum(frequency[term] - 1 for term in terms) / math.sqrt(max(1, len(terms))) for terms in vocabulary]
    best = sorted(range(len(sentences)), key=scores.__getitem__, reverse=True)[:2]
    return " ".join(sentences[index] for index in sorted(best))


TEXT_TOOLS: dict[str, Callable[[str], str]] = {
    "uppercase": str.upper, "lowercase": str.lower, "title case": str.title,
    "reverse": lambda text: text[::-1], "summarize": summarize,
}
TEXT_COMMANDS = "uppercase|lowercase|title case|reverse|summari[sz]e|word count|character count"
TEXT_ALIASES = {
    r"(?:make|turn) (?:this|the following)(?: text)? (?:into )?uppercase": "uppercase",
    r"(?:make|turn) (?:this|the following)(?: text)? (?:into )?lowercase": "lowercase",
    r"count (?:the )?words(?: in (?:this|the following))?": "word count",
    r"count (?:the )?characters(?: in (?:this|the following))?": "character count",
    r"summari[sz]e (?:this|the following)(?: text)?(?: for me)?|give me a summary(?: of this)?": "summarize",
}


def text_reply(action: str, payload: str, session: Session) -> Reply:
    action = action.replace("summarise", "summarize")
    if not payload:
        return Reply("text", f"Give me some text after the colon. Example: {action}: hello world")
    if action == "word count":
        session.last_text = payload
        count = len(WORD.findall(payload))
        return Reply("text", f"{count} word{'s' if count != 1 else ''}.")
    if action == "character count":
        session.last_text = payload
        return Reply("text", f"{len(payload)} Unicode code points, including spaces.")
    session.last_text = TEXT_TOOLS[action](payload)
    if action == "summarize" and session.last_text == payload:
        return Reply("text", f"Already concise: {payload}")
    return Reply("text", session.last_text)


def location_reply(prompt: str, session: Session) -> Reply | None:
    query = (
        re.fullmatch(r"(?:where (?:is|are)|where's|where in the world is|what (?:country|state|region) is) (.+)", prompt)
        or re.fullmatch(r"(?:which (?:country|state|region) is|where can i find) (.+)", prompt)
    )
    follow = re.fullmatch(r"(?:and|what about|how about) (.+)", prompt) if session.last_place else None
    if query or follow:
        place = (query or follow)[1]
        place = re.sub(r"^(?:the )?(?:city|town) of ", "", place)
        place = re.sub(r" (?:located(?: in)?|in)$", "", place)
        place = " ".join(place.replace(",", " ").split())
    elif prompt in PLACE_LOCATIONS or prompt in PLACE_ALIASES:
        place = prompt
    else:
        return None
    if place in {"it", "that", "there"} and session.last_place:
        place = session.last_place
    place = PLACE_ALIASES.get(place, place)
    if place in PLACE_LOCATIONS:
        session.last_place = place
        return Reply("location", PLACE_LOCATIONS[place])
    if place in AMBIGUOUS_PLACES:
        return Reply("location", "Which place do you mean? Add the country or region so I can tell them apart.")
    if query:
        if place.startswith(("my ", "our ", "the nearest ", "the closest ")):
            return Reply("location", "I can't see your location or surroundings. What was the last place you checked, or what area should I use?")
        return Reply("location", "I couldn't place that name. Is it a city, a region, or a landmark? A country or nearby city would help.")
    return None


def small_talk(prompt: str) -> Reply | None:
    if prompt in {"hello", "hi", "hey", "hiya", "yo", "hello there", "hi there", "hey there", "good morning", "good evening", "good afternoon"}:
        return Reply("greeting", "Hi! What's on your mind?")
    social = SMALL_TALK_LEAD.sub("", prompt, count=1)
    social = re.sub(r",? (?:by the way|btw|though)$", "", social)
    last_clause = re.split(r"[,;!?]\s*|\.\s+", social)[-1].strip()
    last_clause = re.sub(r"^(?:and |but )?(?:so |anyway )?", "", last_clause)
    if STATUS.fullmatch(social) or STATUS.fullmatch(last_clause):
        return Reply("greeting", "I'm doing well, thanks for asking. What's on your mind?")
    if prompt in {"not much", "nothing much", "same old", "just chilling"}:
        return Reply("conversation", "Fair enough. Anything you'd like to talk about or try?")
    if re.fullmatch(
        r"(?:what is|what's) (?:your|you) favou?rite colou?r|"
        r"(?:what|which) colou?r (?:is (?:your|you) favou?rite|do you (?:like(?: best)?|prefer))",
        prompt,
    ):
        return Reply("conversation", "I'd pick blue for a chat theme. What's your favorite color?")
    words = set(WORD.findall(prompt))
    if words & {"test", "testing"} and not words & {"not", "never", "don't"} and re.match(r"(?:i|i'm|testing)\b", prompt):
        if any(re.fullmatch(r"spel{2,4}(?:ing)?|typos?", word) for word in words):
            return Reply("conversation", "Go ahead. Try a typo in a topic you know, like 'explain recusion', and I'll check whether I recognize it.")
    return None


def fallback(prompt: str, topic: str | None, session: Session) -> Reply:
    session.unmatched = min(session.unmatched + 1, 3)
    session.suggested_topic = None
    if topic and 5 <= len(topic) <= 32 and re.fullmatch(r"[a-z][a-z -]+", topic):
        matches = get_close_matches(topic, (*TOPICS, *TOPIC_ALIASES), n=2, cutoff=0.84)
        choices = {TOPIC_ALIASES.get(match, match) for match in matches}
        if len(choices) == 1:
            session.suggested_topic = choices.pop()
            return Reply("fallback", f"Did you mean {session.suggested_topic}? Say yes or tell me what you meant.")
    if not WORD.search(prompt):
        return Reply("fallback", "What's on your mind? A sentence or a short question is enough to start.")
    if prompt == "how" or re.match(r"^(?:yes|no|maybe|okay|ok|sure|why|how so|and then)\b", prompt):
        return Reply("fallback", "I need a little more context. What would you like me to explain or do?")
    if topic:
        return Reply("fallback", "I don't have a built-in answer for that topic. What part are you trying to understand? If you have a passage about it, I can summarize it.")
    if re.match(r"^(?:summari[sz]e|rewrite|edit|proofread|translate|shorten)\b", prompt):
        return Reply("fallback", "Paste the text you want to work on and tell me what you'd like to change. For a summary, start with 'summarize:'.")
    if re.match(r"^(?:write|draft|create|make|generate|design)\b", prompt):
        return Reply("fallback", "What would you like to end up with, and who is it for? A short example would help.")
    if re.match(r"^(?:fix|debug|troubleshoot|help me fix|i can't get|i cannot get)\b", prompt):
        return Reply("fallback", "What did you expect to happen, and what happened instead? Include the error message if there is one.")
    if re.match(r"^(?:it|that|this|what about|tell me more|go on)\b", prompt):
        return Reply("fallback", "What are you referring to? Give me the topic or paste the part you want to work on.")
    if re.match(r"^(?:i|i'm|my|we|we're|our)\b", prompt):
        return Reply("fallback", "Do you want to talk more about that, or are you looking for help with something specific?")
    if session.unmatched == 3:
        return Reply("fallback", "Here are three things we can try: ask me to explain recursion, calculate 15% of 240, or paste text after 'summarize:'. Type /help for more.")
    if session.unmatched == 2:
        return Reply("fallback", "What would a useful answer look like: a short explanation, a calculation, or help with some text?")
    return Reply("fallback", "What would you like to know or do with that? A little more detail would help.")


def respond(raw: str, session: Session) -> Reply:
    reply = match_message(raw, session)
    if reply.rule not in {"fallback", "input"}:
        session.unmatched = 0
        session.suggested_topic = None
    return reply


def match_message(raw: str, session: Session) -> Reply:
    if len(raw) > MAX_INPUT:
        return Reply("input", f"Keep each message to {MAX_INPUT} characters or fewer.")
    raw = raw.strip()
    while greeting := GREETING_PREFIX.match(raw):
        raw = raw[greeting.end():]
    if not raw:
        return Reply("input", "Type a message, or use /help for examples.")
    raw = unwrap_prompt(REQUEST_PREFIX.sub("", raw, count=1))
    literal = re.fullmatch(rf"({TEXT_COMMANDS})\s*:[ \t]*(.*)", raw, re.I | re.S)
    if literal:
        return text_reply(literal[1].lower(), literal[2], session)
    if ":" in raw:
        action, payload = raw.split(":", 1)
        for phrase, tool in TEXT_ALIASES.items():
            if re.fullmatch(phrase, canonical(action)):
                return text_reply(tool, payload.lstrip(), session)

    notation = SUPERSCRIPT.sub(lambda match: f"^({match[1].translate(SUPERSCRIPT_DIGITS)})", raw)
    message = re.sub(r"^whats ", "what's ", canonical(notation))
    prompt = unwrap_prompt(ENDING.sub("", message).strip())
    prompt = re.sub(r",? (?:please|for me)$", "", prompt)
    if session.suggested_topic and prompt in {"yes", "yes please", "yeah", "yep", "correct", "that's right"}:
        return Reply("definition", TOPICS[session.suggested_topic])
    if message in {"/quit", "quit", "exit", "bye", "goodbye"} or prompt in {"bye", "goodbye"}:
        return Reply("exit", "Goodbye!", exit=True)
    if message == "/reset":
        session.notes.clear()
        session.last_number = None
        session.last_text = None
        session.last_place = None
        return Reply("memory", "Session cleared.")
    if message == "/memory":
        notes = "\n".join(f"- {key} = {value}" for key, value in session.notes.items())
        return Reply("memory", notes or "There are no saved notes in this session.")
    if message == "/help" or prompt in {"help", "what can you do", "how can you help"}:
        return Reply("help", HELP)
    if message.startswith("/") and re.match(r"/[a-z]", message):
        return Reply("command", "Unknown command. Try /help, /memory, /reset, or /quit.")

    # Keep note values and template topics in the user's original case.
    remember = re.fullmatch(r"remember\s+(?:that\s+)?(.+?)\s+(?:is|as)\s+(.+)", raw, re.I | re.S)
    name = re.fullmatch(r"my\s+name\s+is\s+(.+)", raw, re.I | re.S)
    if remember or name:
        key = ENDING.sub("", canonical(remember[1])).strip() if remember else "my name"
        value = (remember[2] if remember else ENDING.sub("", name[1])).strip()
        if not key or not value or len(key) > 80 or len(value) > 400 or len(value.splitlines()) != 1:
            return Reply("memory", "Use a short key and a single-line value. Example: remember that my city is Copenhagen.")
        if key not in session.notes and len(session.notes) >= MAX_MEMORIES:
            return Reply("memory", f"This session has {MAX_MEMORIES} notes. Use 'forget <key>' to make room.")
        session.notes[key] = value
        return Reply("memory", f"I'll remember {key} for this session.")
    if re.match(r"remember\b", prompt):
        return Reply("memory", "Use this form: remember that my favorite color is blue.")
    forget = re.fullmatch(r"forget(?: that)? (.+)", prompt)
    if forget:
        removed = session.notes.pop(forget[1], None)
        return Reply("memory", f"Forgot {forget[1]}." if removed is not None else "I don't have a note under that key.")
    recall = re.fullmatch(r"(?:recall|what did i say about) (.+)", prompt)
    question = (
        QUESTION.fullmatch(prompt)
        or re.fullmatch(r"how (?:does|do) (.+) work", prompt)
        or re.fullmatch(r"(?:tell me|explain(?: to me)?|i was wondering) what (.+) (?:is|are)", prompt)
    )
    key = recall[1] if recall else question[1] if question else None
    if key in session.notes:
        return Reply("memory", f"You saved {key} as {session.notes[key]}.")
    if recall or key == "my name":
        return Reply("memory", "I don't have that saved. Try: remember that my name is Alex.")

    numeric_prompt = MATH_REQUEST.sub("", prompt, count=1).replace("−", "-")
    numeric_prompt = re.sub(r" (?:equal|make)$", "", numeric_prompt)
    direct = re.fullmatch(rf"(add|subtract|multiply|divide) ({NUMBER}) (and|to|from|by) ({NUMBER})", numeric_prompt)
    if direct:
        action, left, connector, right = direct.groups()
        connectors = {"add": {"and", "to"}, "subtract": {"from"}, "multiply": {"by"}, "divide": {"by"}}
        if connector in connectors[action]:
            if connector == "from":
                left, right = right, left
            return math_reply(f"({left}){FOLLOW_OPERATORS[action]}({right})", session)
    follow = re.fullmatch(r"(?:and |then )?(add|subtract|multiply|divide)(?: by)? (.+)", numeric_prompt)
    if follow and re.search(r"[0-9]", follow[2]):
        if session.last_number is None:
            return Reply("math", "Give me a starting calculation first. Example: calculate 10 + 2.")
        return math_reply(f"({session.last_number}){FOLLOW_OPERATORS[follow[1]]}({math_expression(follow[2])})", session)
    follow_text = re.fullmatch(rf"(?:(?:make|turn) (?:it|that) (?:into )?({TEXT_COMMANDS})|({TEXT_COMMANDS}) (?:it|that))", prompt)
    if follow_text:
        if session.last_text is None:
            return Reply("text", "Give me some text first. Example: lowercase: HELLO WORLD.")
        return text_reply(follow_text[1] or follow_text[2], session.last_text, session)
    if re.fullmatch(TEXT_COMMANDS, prompt):
        return text_reply(prompt, "", session)

    calculation = numeric_prompt
    percentage = re.fullmatch(rf"({NUMBER})\s*(?:%|percent)\s+of\s+({NUMBER})", calculation)
    if percentage:
        rate, amount = percentage.groups()
        return math_reply(f"({rate}) / 100 * ({amount})", session)
    conversion = re.sub(r"^(?:convert\s+)", "", calculation)
    units = re.fullmatch(rf"({NUMBER})\s*([a-z°]+)\s+(?:to|in|into)\s+([a-z°]+)", conversion)
    if units:
        return convert(*units.groups())
    how_many = re.fullmatch(rf"how many ([a-z°]+) (?:are )?in ({NUMBER})\s*([a-z°]+)", prompt)
    if how_many:
        target, amount, source = how_many.groups()
        return convert(amount, source, target)
    if calculation.startswith("convert ") or calculation == "convert":
        return Reply("conversion", "Use an amount, a source unit, and a target unit. Example: convert 72 F to C.")
    expression = math_expression(calculation)
    if re.fullmatch(r"[0-9e. +*/%()\-]+", expression) and re.search(r"[0-9]", expression):
        return math_reply(expression, session)
    if re.match(r"^(?:calculate|compute|evaluate|solve|work out)\b", prompt):
        return math_reply(expression, session)

    if prompt in {"what time is it", "what's the time", "current time", "time"}:
        return Reply("clock", datetime.now().strftime("It's %H:%M local time."))
    if prompt in {"what day is it", "what's the date", "what is today's date", "today's date", "date"}:
        return Reply("clock", f"Today is {datetime.now():%A, %Y-%m-%d} local time.")
    if prompt in {"who are you", "what are you", "what's your name", "what is your name", "are you an ai"}:
        return Reply("identity", "I'm a Python chatbot. My replies come from pattern matching, lookup tables, and a few built-in tools.")
    if reply := small_talk(prompt):
        return reply
    if prompt in {"thanks", "thank you", "thanks a lot", "thank you so much", "cheers"}:
        return Reply("thanks", "You're welcome!")
    if prompt in {"tell me a joke", "joke", "make me laugh"}:
        return Reply("joke", "Why do programmers confuse Halloween and Christmas? Because Oct 31 equals Dec 25.")
    if re.fullmatch(r"(?:i am|i'?m|i feel|i've been feeling) (?:(?:a bit|pretty|really|so|very|kind of) )?(?:sad|stressed|frustrated|overwhelmed|tired|upset)(?: today| right now| lately)?", prompt):
        return Reply("conversation", "That sounds rough. If you'd like, tell me what happened or what's on your mind.")
    topic = re.sub(r"^(?:an?|the) ", "", key) if key else prompt
    definition = TOPICS.get(TOPIC_ALIASES.get(topic, topic))
    if definition:
        return Reply("definition", definition)
    if reply := location_reply(prompt, session):
        return reply

    email = re.fullmatch(r"(?:draft|write) (?:an )?email about\s+(.+)", raw, re.I)
    if email:
        topic = email[1].rstrip(".!?").strip()
        if topic:
            return Reply("email", f"Subject: {topic[:1].upper()}{topic[1:]}\n\nHi [Name],\n\nI'm writing about {topic}. [Add the relevant details here.]\n\n[Say what you need from the recipient and by when.]\n\nThanks,\n[Your name]")
    plan = re.fullmatch(r"(?:help me plan|make (?:a )?plan for)\s+(.+)", raw, re.I)
    if plan:
        topic = plan[1].rstrip(".!?").strip()
        if topic:
            return Reply("plan", f"Plan for {topic}\n\n1. Describe what a good outcome would look like.\n2. Write down your deadline, budget, and constraints.\n3. Choose the first action you can complete today.\n4. Set a time to check progress and adjust the plan.")

    return fallback(prompt, topic if key else None, session)


def display(reply: Reply, trace: bool) -> None:
    safe_text = "".join(
        character if character.isprintable() or character in "\n\t" else ascii(character)[1:-1]
        for character in reply.text
    )
    print(f"[{reply.rule}] {safe_text}" if trace else safe_text, flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trace", action="store_true", help="show the rule that matched")
    parser.add_argument("message", nargs="*", help="respond once instead of starting a session")
    args = parser.parse_args()
    session = Session()
    if args.message:
        display(respond(" ".join(args.message), session), args.trace)
        return 0

    interactive = sys.stdin.isatty()
    if interactive:
        print("Rules-based chat. Type /help for examples or /quit to exit.")
    try:
        while True:
            if interactive:
                print("You > ", end="", flush=True)
            line = sys.stdin.readline(MAX_INPUT + 2)
            if not line:
                if interactive:
                    print()
                return 0
            reply = respond(line.removesuffix("\n"), session)
            while len(line) == MAX_INPUT + 2 and not line.endswith("\n"):
                line = sys.stdin.readline(MAX_INPUT + 2)
            display(reply, args.trace)
            if reply.exit:
                return 0
    except KeyboardInterrupt:
        if interactive:
            print("\nGoodbye!")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
