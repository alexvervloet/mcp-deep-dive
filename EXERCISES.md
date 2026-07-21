# Exercises: make the learning stick

Reading code teaches you less than *predicting* what it will do and then checking.
This file turns each section of the [README](README.md) into a few quick
active-recall prompts.

How to use it: work the section first, then come back. **Commit to an answer
before you run or reveal.** The prediction is where the learning happens. Answers
are hidden behind ▸ toggles.

> Sections 2-7 and 9-10 are **(offline)**: a server and client talk with no model,
> so they need no key and cost nothing. Only Section 8 and the capstone call an LLM.

---

## Section 2: The protocol **(offline)**

**Recall.** Name the three roles (host, client, server) and say which one
contains a model.

<details><summary>▸ Answer</summary>

- **Host**: the app the user uses (Claude Desktop, an IDE, the capstone). Holds
  one or more clients.
- **Client**: a connector inside the host; one connection to one server.
- **Server**: a separate program exposing capabilities. **None** of them *is* the
  model in the protocol sense, and the **server contains no model at all**; it
  just answers requests. The model lives in the host.
</details>

**Recall.** The three primitives differ by *who is in control*. Match tool /
resource / prompt to model-controlled / app-controlled / user-controlled.

<details><summary>▸ Answer</summary>

- **Tool** → **model**-controlled (the model decides to call it to act).
- **Resource** → **app**-controlled (your app decides to read the data into context).
- **Prompt** → **user**-controlled (the user picks the template, e.g. a slash-command).
</details>

---

## Section 3: Your first server **(offline)**

**Predict, then run.** `examples/02_first_server_and_client.py` uses the raw SDK.
After `stdio_client(...)` spawns the server, what two calls actually *do the work*
of discovering and running a tool?

<details><summary>▸ Answer</summary>

`session.list_tools()` (the `tools/list` request, to discover what's available) and
`session.call_tool(name, args)` (the `tools/call` request, to run one). Everything
before them (`stdio_client`, `ClientSession`, `initialize()`) is just setting up
the pipe and handshake.
</details>

---

## Section 4: Client lists & calls **(offline)**

**Recall.** This is the example to sit with. What single claim does it prove, and
why does it need no LLM?

<details><summary>▸ Answer</summary>

That **you write a server once and any MCP client can discover and use its tools** 
connect → list → call. No LLM is needed because *calling a tool* is just a protocol
request/response; the model only matters later, when something has to *decide* which
tool to call.
</details>

---

## Section 5: Resources **(offline)**

**Predict.** A resource and a tool can both return the body of a note. What's the
real difference between them?

<details><summary>▸ Answer</summary>

**Control.** A **resource** is read-only data your *application* chooses to read and
drop into context (like a GET); a **tool** is something the *model* chooses to call
to act. `notes://note/{key}` is a *templated* resource: the URI itself carries the
argument.
</details>

---

## Section 6: Prompts **(offline)**

**Recall.** Why serve a prompt template *over MCP* instead of hard-coding it in the
host?

<details><summary>▸ Answer</summary>

Because **the server is the expert on its own data**. The team running the server
can ship and improve a great "summarize my notes" prompt, with the right field names and right
tone: server-side, and every host gets the improvement for free without
re-implementing it. The host just lists and offers what's available.
</details>

---

## Section 7: A multi-tool server **(offline)**

**Predict, then run.** `examples/06_multi_tool_server.py` connects to a server with
several tools. What did you have to change in the **client** to get the extra tools?

<details><summary>▸ Answer</summary>

**Nothing.** The server grew; `tools/list` simply returns more. Capability lives in
the server, and any client/host gets it for free. That's the protocol paying off.
Note that `save_note` has a **side effect** (writes a file), so flag it for approval
once a model is driving.
</details>

---

## Section 8: An LLM in the loop

**Recall.** When the host hands the server's tools to the model, does the model know
they came from an MCP server? Why does the answer matter?

<details><summary>▸ Answer</summary>

**No.** To the model a tool is just a name, description, and JSON Schema, identical
to a local function. That **invisibility is the whole point of MCP**: write the
server once and any model on any provider can use it, with the agent loop unchanged.
</details>

**Predict.** Compare `host/loop.py` to the Agents deep dive's loop. What's the one
real difference?

<details><summary>▸ Answer</summary>

Only *where the tools come from and how they run*: discovered via `tools/list` and
executed via `tools/call` over the protocol, instead of being local Python
functions. The loop itself (ask model, run requested tools, feed results back,
repeat until done, with a `max_steps` ceiling) is the same.
</details>

---

## Section 9: Transports **(offline)**

**Recall.** Why does `examples/08_http_transport.py` need *two terminals* when the
stdio examples needed only one?

<details><summary>▸ Answer</summary>

A **stdio** server is *launched by the client* as a subprocess: one process tree,
one terminal. An **HTTP** server is a standing service you start *separately* and
connect to by URL, so you run the server in one terminal and the client in another.
Same `tools/list`/`tools/call`; different transport.
</details>

---

## Section 10: Security **(offline)**

**Predict, then run.** `examples/09_security.py` connects to a hostile server. Name
the two channels through which a malicious server can attack your host, and why you
can see the attack with *no LLM*.

<details><summary>▸ Answer</summary>

(1) A malicious **tool/resource description** that tries to hijack the model when the
host puts it in context, and (2) a malicious **tool result** that smuggles
instructions back. You can see both in the **raw data** the server hands you 
which is exactly why you inspect it *before* a model acts on it. A server you didn't
write is untrusted input, just like a web page in the injection dive.
</details>

**Recall.** Name two defenses from §10 that don't depend on the model behaving.

<details><summary>▸ Answer</summary>

Any two of: **least privilege** (don't connect to servers you don't trust; limit
what each tool can touch), **human approval** for side-effecting tools, and
**treating all server text as untrusted** (guardrails on tool results). These work
*around* the model because you can't make the model un-trickable.
</details>

---

## Section 11: Wiring into real hosts

**Recall.** What two things in the Claude Desktop config trip people up most?

<details><summary>▸ Answer</summary>

**Absolute paths** (to both the venv's `python` and the server script; relative
paths fail), and **restarting the host** so it re-reads the config. After that, the
same tools/resources/prompts the §4 client saw appear inside Claude Desktop.
</details>

---

## Capstone: `assistant.py`

**Do.** Run `secrun python hands_on/assistant.py` and ask it something that needs a tool
(e.g. *"What's the Plus plan cost for a full year?"*). Watch the trace. How many
processes are involved, and where does each tool actually run?

<details><summary>▸ Answer</summary>

Two: the **host** (this script + the model) and the **server** subprocess. Each tool
runs **in the server**, reached over MCP. The host just asks the model what to do,
relays the `tools/call`, and feeds the result back. The model never touches the
tool's code.
</details>

**Stretch.** Write your own tiny `FastMCP` server with one tool you'd actually use,
then run `secrun python hands_on/assistant.py --server path/to/your_server.py`. When the
assistant calls *your* tool with no other change to the capstone, the "write once,
use anywhere" idea has landed. Then try `save_note` and watch the approval prompt
fire. That's the §10 security lesson on a live path.

---

### Where to take it next

Point a *real* host at one of your servers (the §11 Claude Desktop / Claude Code
config) and use it in an actual conversation. The first time a tool you wrote here
shows up inside a chat app you didn't write, the whole reason MCP exists is obvious.
