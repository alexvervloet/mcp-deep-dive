# MCP (Model Context Protocol) — A Guided Deep Dive

A hands-on playground for learning the **Model Context Protocol** from the ground
up — the open standard for handing an LLM *tools, data, and prompts* from a
separate process. You'll build MCP servers, write a client that talks to them,
and finally let a model drive those tools over the protocol — understanding every
moving part: the three primitives (tools, resources, prompts), the JSON-RPC
handshake, stdio vs. HTTP transports, wiring a server into Claude Desktop / Claude
Code, and the security model. No framework magic beyond the official `mcp` SDK
itself — just enough code to *see* how it works.

The thing that makes this repo click: **most of it runs offline and free.** A
server and a client talk to each other with **no model involved** — so Sections
2–7 (your first server, the client, resources, prompts, a multi-tool server) need
no API key at all. You only need a provider once you put an LLM "host" in the loop
(Section 8 onward).

This repo is **standalone**: it teaches everything it needs on its own. It goes far
deeper than the "Bonus — MCP" section of the
[Agents deep dive](https://github.com/Ailuue/agents-deep-dive) (Section 8 here *is*
the agent loop, with tools served over MCP), and its security section builds on the
[Prompt Injection deep dive](https://github.com/Ailuue/prompt-injection-deep-dive)
— but its code depends on neither.

Like its siblings, it's meant to be *walked through*. Each section ends with
something to run; the first six run **offline and free**. [EXERCISES.md](EXERCISES.md)
has a predict-then-run prompt for each section.

---

## 0. The one big idea

> **MCP is a standard way to hand an LLM tools, data, and prompt templates from a
> *separate process*. Write the server once, and any MCP-speaking client or host
> can discover and use it.**

That's the whole repo. Before MCP, every app re-implemented its own tools and
glued them to its own model in its own way. MCP makes the *connector* standard: a
**server** exposes capabilities; a **client** (inside a **host** like Claude
Desktop, an IDE, or the capstone here) connects and uses them — over plain
JSON-RPC. The model never knows or cares where a tool came from; to it, a tool is
just a name, a description, and a schema. Everything below — resources, prompts,
HTTP transport, security — is a small addition to that one idea. Hold onto it and
none of this feels complicated.

---

## 1. Setup (5 minutes)

```bash
# 1. Create an isolated Python environment
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 2. Install dependencies (the official MCP SDK + a provider SDK)
pip install -r requirements.txt

# 3. Copy the env file — you do NOT need a key for Sections 2-7
cp .env.example .env

# 4. Confirm everything is wired up (makes no API call, costs nothing)
python check_setup.py
```

The `mcp` SDK and Python 3.10+ are required for **everything**. A `PROVIDER` and
its key are required **only** for the LLM-in-the-loop sections (8 + the capstone):

| `PROVIDER` | Used for | Key needed |
|------------|----------|------------|
| *(none)* | Sections 2–7 — server↔client with **no model**. Fully offline. | none |
| `openai` (default) | The host loop (§8+): OpenAI chat + function calling. | `OPENAI_API_KEY` |
| `claude` | The host loop (§8+): Claude messages + tool use. | `ANTHROPIC_API_KEY` |

> 💡 **MCP-first means free-first.** The protocol is the subject, and the protocol
> doesn't need a model. You can learn the entire mechanism — servers, the three
> primitives, transports, even the security model — without spending a cent. The
> LLM only shows up at the end, to *use* what you built.

---

## 2. The protocol in one page

```bash
python examples/01_protocol.py
```

MCP is a small, boring idea, and it's worth getting the vocabulary straight before
launching anything:

- **Host** — the app the user interacts with (Claude Desktop, an IDE, the capstone
  here). It contains one or more **clients**.
- **Client** — a connector inside the host that holds *one* connection to *one*
  server and speaks the protocol.
- **Server** — a separate program that exposes capabilities. It contains **no
  model**; it just answers requests.

They talk over **JSON-RPC 2.0** (plain JSON request/response) across a **transport**
(a pipe): `stdio` (a local subprocess) or streamable `HTTP/SSE` (a network
service). And a server exposes exactly **three primitives**, which the rest of the
repo walks through one at a time:

| Primitive | What it is | Who's in control |
|-----------|-----------|------------------|
| **Tool** | A function the model can *call* to act | **Model**-controlled |
| **Resource** | Read-only *data* exposed by URI (like a GET) | **App**-controlled |
| **Prompt** | A reusable, parameterized prompt *template* | **User**-controlled |

---

## 3. Your first server, and the raw client

```bash
python examples/02_first_server_and_client.py
```

Section 2 showed the JSON messages; here you send real ones, using the official
SDK's client API with **no wrapper**, so you see the actual ceremony exactly as the
SDK docs describe it. The server ([servers/calculator.py](servers/calculator.py))
is a dozen lines — a `FastMCP` instance with one `@mcp.tool()` function. The client
spawns it as a subprocess over stdio, runs the `initialize` handshake, then
`list_tools()` and `call_tool(...)`. This is the only example that uses the raw API
directly — after this we use a small `MCPClient` wrapper so the *protocol* stays in
focus, not the async boilerplate.

---

## 4. A client that lists and calls a tool

```bash
python examples/03_client_calls_tool.py
```

**The free-first runnable to really sit with.** Same idea as §3 — a client lists and
calls a tool — but through the small [`MCPClient`](client/mcp_client.py) wrapper, so
the steps stand out: **connect → list → call**. It proves the core claim of the
whole repo: *you write a server once, and any MCP-speaking client can discover and
use its tools — with no LLM anywhere.* Everything later is a small addition to
exactly this.

---

## 5. Resources — read-only data for the model

```bash
python examples/04_resources.py
```

A tool is something the model *calls* to act. A **resource** is read-only **data**
the server publishes by URI — closer to a GET endpoint than a function call. The
distinction is about control: *your application* decides to read a resource and put
its contents into the model's context; the model doesn't invoke it. The
[notes server](servers/notes.py) exposes a static resource (`notes://all`) and a
*templated* one (`notes://note/{key}`); the example lists and reads them — still
with no LLM.

---

## 6. Prompts — reusable templates served by MCP

```bash
python examples/05_prompts.py
```

The third primitive. A **prompt** is a parameterized prompt *template* the server
owns and the user picks — think of the slash-commands in a chat app (`/summarize`).
Why serve prompts over a protocol instead of hard-coding them in the host? Because
**the server is the expert on its own data**: the team that runs the notes server
can ship a great "summarize my notes" prompt — correct field names, the right tone
— and improve it server-side without every host re-implementing it. The host just
lists what's available and offers it to the user.

---

## 7. A real, many-tool server

```bash
python examples/06_multi_tool_server.py
```

So far, one tool at a time. Real servers expose a handful of related tools, and the
client discovers them all the same way. This connects to
[servers/toolbox.py](servers/toolbox.py) — calculator, search_notes, word_count,
save_note, plus resources and a prompt — and exercises several over one connection.
Two things to notice: you **didn't change the client** to get new tools (the server
grew; `tools/list` just returns more), and `save_note` has a **side effect** (it
writes a file) — which is exactly the kind of tool you'll gate behind approval once
a model is driving (§8, §11).

---

## 8. Put an LLM in the loop

```bash
python examples/07_llm_calls_mcp_tools.py     # needs a key
```

The first example that costs money — everything before was offline. Now a **model
drives the MCP tools**: the host lists the server's tools, describes them to the
model, and when the model asks to call one, the host runs it over the protocol and
feeds the result back. **This is the agent loop** from the Agents deep dive, with
one change — the tools live in a separate process behind MCP. The headline: the
model has *no idea* the tools came from an MCP server. To it they're just
names + descriptions + schemas. That invisibility is the reason MCP exists. The
loop lives in [host/loop.py](host/loop.py), and it carries over the agent-dive
safety logic: a `max_steps` ceiling, approval for side-effecting tools, and
in-band error results so a failing tool doesn't crash the host.

---

## 9. Transports — stdio vs. HTTP

```bash
# terminal 1: start the HTTP server and leave it running
python servers/calculator_http.py
# terminal 2:
python examples/08_http_transport.py
```

The stdio examples *launched* the server themselves as a subprocess. An **HTTP**
server is different: it's already running somewhere and you connect to it by URL.
Same tools, same `tools/list` / `tools/call` — just a network transport
underneath. Rule of thumb: **stdio** for local tools that ship with the host (a
subprocess on your machine); **streamable HTTP** for a shared service multiple
hosts connect to over the network.

---

## 10. Security — MCP + prompt injection

```bash
python examples/09_security.py     # offline, no key
```

MCP is a **trust decision**. When your host connects to a server, that server's
tool descriptions and resource contents flow straight into your model's context —
and the model's tool calls get executed by your host. A server you didn't write is
**untrusted input**, exactly like a web page in the
[Prompt Injection deep dive](https://github.com/Ailuue/prompt-injection-deep-dive).
This connects to [servers/sneaky.py](servers/sneaky.py) — a deliberately hostile
server — and shows the two attacks (a malicious tool *description* that tries to
hijack the model, and a tool *result* that smuggles instructions) and the defenses:
least privilege, human approval for side-effecting tools, and treating every
server's text as untrusted. No LLM needed — you can see the malice in the raw data,
which is the whole point.

---

## 11. Wiring your server into a real host

The payoff of a standard protocol: a server you wrote here works in *real* hosts
unchanged. To use [servers/toolbox.py](servers/toolbox.py) in **Claude Desktop**,
add it to the MCP config (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "toolbox": {
      "command": "/absolute/path/to/.venv/bin/python",
      "args": ["/absolute/path/to/mcp-deep-dive/servers/toolbox.py"]
    }
  }
}
```

In **Claude Code**, register it from the CLI:

```bash
claude mcp add toolbox -- /absolute/path/to/.venv/bin/python servers/toolbox.py
```

Restart the host and your tools, resources, and prompts appear — the same ones the
client in §4 saw. You can also point a host at *existing* third-party servers
(filesystem, GitHub, databases) the same way. The `mcp` CLI (installed via
`mcp[cli]`) can inspect or run a server during development: `mcp dev servers/toolbox.py`.

---

## The capstone: `assistant.py`

Everything assembled into one runnable command: a multi-turn chat assistant whose
**every capability comes from an MCP server**. The model holds no tools of its own;
it discovers them over the protocol and calls them over the protocol. Swap the
server and the assistant gains new powers without touching the capstone.

```bash
# interactive chat (Ctrl-D or "quit" to exit):
python hands_on/assistant.py

# one-shot question, then exit:
python hands_on/assistant.py "What does the Plus plan cost for a year?"

# point at a different MCP server:
python hands_on/assistant.py --server servers/notes.py

# auto-approve side-effecting tools (skip the prompt before save_note):
python hands_on/assistant.py --yes
```

Read [hands_on/assistant.py](hands_on/assistant.py): it's just the client
(`MCPClient`), the host loop (`run_host`), and a human-approval callback wired to a
CLI — the whole repo in one file. **Suggested exercise:** write your own small
`FastMCP` server (one tool you'd actually use) and point the capstone at it with
`--server`. When the assistant calls *your* tool with no other change, MCP has
clicked.

---

## Where to go next

You've built servers, a client, and a host. The frontier is more of the same idea,
at more scale:

- **Sampling & elicitation** — newer MCP features that let a *server* ask the host's
  model to generate text, or ask the *user* for input mid-call.
- **OAuth & remote servers** — authenticating to hosted MCP servers you don't run.
- **Real third-party servers** — wire the official filesystem / GitHub / Postgres
  servers into Claude Desktop and feel the "write once, use anywhere" payoff.
- **Streaming results** & long-running tools — progress notifications over the
  protocol.
- **Building a host UI** — the capstone is a REPL; a real host renders tools,
  resources, and prompt slash-commands as UI.

---

## From teaching code to production

The teaching shortcuts here are exactly what you'd harden once an MCP host is on a
live path:

| This repo's teaching shortcut | In production |
|-------------------------------|---------------|
| Connect to any server script | **Vet and pin** servers; treat unknown servers as untrusted code |
| Approval is a terminal `y/N` prompt | A real **authorization** layer with policy, audit, and per-tool scopes |
| Tool/resource text is read as-is | **Guardrails** on everything a server returns — it's untrusted input (§10) |
| stdio subprocess on your machine | **Auth'd HTTP** servers with TLS, rate limits, and least-privilege creds |
| The host loop prints a trace | **Observability** — structured traces of every tool call, with cost |
| One server, hard-coded | A **registry** of approved servers, versioned and health-checked |

The general ops machinery — observability, cost, reliability, caching, guardrails,
prompt versioning, eval gates — is built from scratch and wired into one running app
in **[Production](https://github.com/Ailuue/ai-in-production-deep-dive)** (#8 in the
series), which runs offline on a mock provider.

---

## File map

```
check_setup.py              ← run first: Python, the mcp SDK, provider, key
README.md                   ← this guide
EXERCISES.md                ← predict-then-run prompts, one per section
servers/                    ← MCP servers (the capability side)
  calculator.py             ← the minimal one-tool server (stdio)
  calculator_http.py        ← the same, over streamable HTTP (Section 9)
  notes.py                  ← all THREE primitives: tools, resources, prompts
  toolbox.py                ← a realistic multi-tool server (used by the capstone)
  sneaky.py                 ← a deliberately HOSTILE server (Section 10)
client/                     ← the client side
  mcp_client.py             ← MCPClient: a small readable wrapper over the SDK
host/                       ← the LLM side
  providers.py              ← neutral tool schema + run_turn for openai / claude
  loop.py                   ← run_host: the agent loop, tools served over MCP
hands_on/
  assistant.py              ← capstone: an MCP-powered, multi-turn chat assistant
examples/
  01_protocol.py            ← the protocol & vocabulary in one page (offline)
  02_first_server_and_client.py ← the raw SDK client, once (offline)
  03_client_calls_tool.py   ← connect → list → call, via MCPClient (offline)
  04_resources.py           ← read-only data by URI (offline)
  05_prompts.py             ← server-owned prompt templates (offline)
  06_multi_tool_server.py   ← many tools over one connection (offline)
  07_llm_calls_mcp_tools.py ← a model drives the tools (needs a key)
  08_http_transport.py      ← connect to a server over HTTP (offline)
  09_security.py            ← a hostile server; attacks & defenses (offline)
```

(`workspace/` is created by the notes/toolbox servers' `save_note` tool and is
git-ignored.)

---

## Troubleshooting

Run `python check_setup.py` first — it catches most problems. Then, by symptom:

| What you see | What it means / the fix |
|--------------|-------------------------|
| `ModuleNotFoundError: mcp` | The SDK isn't installed. `pip install -r requirements.txt` (it pulls `mcp[cli]`). |
| A server example just hangs | A stdio server talks over stdin/stdout — **don't** run `servers/*.py` directly expecting output; run the **example** (or the capstone), which launches the server for you. |
| `08_http_transport.py` can't connect | The HTTP server isn't up. Start `python servers/calculator_http.py` in another terminal first (it stays running on `:8000`). |
| `PROVIDER=... needs ... in .env` | Only the LLM sections (8 + capstone) need a key. Sections 2–7 run with none. Add the key or stick to the offline examples. |
| Import errors from `host` / `client` / `servers` | Run from the repo root (`python examples/03_...py`), not from inside a subfolder — the examples add the repo root to `sys.path`. |
| Claude Desktop doesn't see my server | Use **absolute** paths to the venv's python *and* the script in the config, then fully restart the app. `mcp dev servers/toolbox.py` helps debug locally. |
| `SyntaxError` / odd type errors on startup | You're likely on Python 3.9 or older; this repo needs 3.10+. `check_setup.py` confirms your version. |

Still stuck? Every file is small and self-contained — open it, read the docstring
at the top, and run the matching example. [client/mcp_client.py](client/mcp_client.py)
and [host/loop.py](host/loop.py) are the whole story.

---

## The series

This is one of eight standalone, hands-on deep dives into building with LLM APIs.
Each one stands on its own — its own setup, examples, and capstone — and they all
share the same house style: provider-agnostic where it makes sense, built from
scratch (no frameworks), offline-first examples, and a real capstone. Do them in
any order; this sequence builds naturally:

1. [OpenAI API](https://github.com/Ailuue/openai-api-deep-dive) — the API from zero
2. [Claude API](https://github.com/Ailuue/claude-api-deep-dive) — the same ideas, the Anthropic way
3. [Prompt Engineering](https://github.com/Ailuue/prompt-engineering-deep-dive) — shape model behavior with better prompts
4. [RAG](https://github.com/Ailuue/rag-deep-dive) — answer questions over your own documents
5. [Evals](https://github.com/Ailuue/evals-deep-dive) — measure whether a change actually helps
6. [Agents](https://github.com/Ailuue/agents-deep-dive) — give a model tools and a loop so it can act
7. [Prompt Injection & Guardrails](https://github.com/Ailuue/prompt-injection-deep-dive) — attack and defend all of the above
8. [Production](https://github.com/Ailuue/ai-in-production-deep-dive) — operate one app end to end

**MCP is a bonus dive in the series.** It slots most naturally right after
[Agents](https://github.com/Ailuue/agents-deep-dive) (#6) — Section 8 here is that
dive's loop with tools served over MCP — and its security section (§10) builds on
[Prompt Injection & Guardrails](https://github.com/Ailuue/prompt-injection-deep-dive)
(#7).
