# Chapter 14: A Protocol, Not a Product

*This is the textbook chapter for the MCP deep dive, a bonus dive that slots after [Agents](../agents-deep-dive/TEXTBOOK.md). The [README](README.md) is the lab manual; this is the lecture. It covers the integration problem MCP was invented to dissolve, the older standards whose playbook it copies, what the three primitives actually divide up, and why connecting to a server you did not write is a trust decision wearing a convenience's clothes.*

---

## 14.1 The problem no one wants to solve twice

By 2024, a pattern had set in across the AI industry, and it was wasteful in a familiar way. Every team building a tool-using assistant was writing the same glue over and over. You wanted your model to read from Google Drive, so you wrote a Drive integration. You wanted it to query your Postgres database, so you wrote a database integration. You wanted GitHub, Slack, a filesystem, a ticketing system, and you wrote each one, in your framework, against your model, in your particular way. The team down the hall, building a different assistant, wrote all of the same integrations again, differently.

Multiply it out and the shape of the waste becomes clear. If there are M applications that want tools and N tools worth connecting to, the naive world requires roughly M times N integrations, each one bespoke, each one maintained separately, each one breaking on its own schedule. Every new tool has to be wired into every app; every new app has to re-wire every tool. This is not a new kind of problem, and that is the good news, because the industry has solved this exact shape before.

The Model Context Protocol, which Anthropic introduced in November 2024, is the standard answer to the M-times-N problem. Its one big idea is small and, once you see it, almost obvious:

> **MCP is a standard way to hand a language model tools, data, and prompt templates from a separate process. Write the server once, and any MCP-speaking client can discover and use it.**

Standardize the connector, and M times N collapses to M plus N. A tool's author writes one MCP server. An application's author writes one MCP client. Any client can talk to any server, because they share an agreed wire format. The model on the other end never knows or cares where a tool came from; to it, a tool is still just a name, a description, and a schema, exactly as it was in Chapter 6. That invisibility is the entire point, and it is why MCP got adopted quickly: within months, OpenAI and others had embraced the same protocol, which is the strongest possible signal that a standard has done its job, when your competitors implement it too.

## 14.2 The standards that wrote this playbook

MCP is often introduced with an analogy, "USB-C for AI," and the analogy is decent: one connector shape, and any device speaks to any host. But the more instructive precedent, for anyone who wants to understand *why* MCP is shaped the way it is, is a protocol from Microsoft called the Language Server Protocol.

Before LSP, code editors had the M-times-N problem in its purest form. Each editor (VS Code, Vim, Emacs, and the rest) needed language-specific smarts (autocomplete, go-to-definition, error checking) for each programming language (Python, Rust, Go, and dozens more). Editors times languages, each pair a separate, painful integration, which is why good support for your language in your editor was a coin flip. In 2016, Microsoft factored the problem: a *language server* implements the smarts for one language, once, and speaks a standard protocol; any editor that speaks the protocol gets full support for that language for free. Editors times languages became editors plus languages, and the ecosystem exploded, because now writing support for a new language benefited every editor at once.

MCP copies this playbook deliberately, one layer up. Swap "editor" for "AI application" and "language server" for "tool server" and the diagram is identical. There are older ancestors too (ODBC did it for databases in the early 1990s, letting any application talk to any database through one driver interface), and the recurrence is the lesson: whenever you have many consumers and many providers of some capability, a standard protocol in the middle is how the combinatorial mess becomes additive. MCP is not a clever new AI idea. It is a well-worn systems idea, applied to a new domain at exactly the moment the domain needed it.

## 14.3 Three roles, one conversation

The vocabulary is small and worth getting exactly right, because casual usage blurs it. Three roles participate.

The **host** is the application the person actually interacts with: a desktop assistant, an IDE, the capstone in this dive. The host is where the model lives and where the human types.

A **client** is a connector living inside the host. It holds exactly one connection to exactly one server and speaks the protocol on the host's behalf. A host with three servers connected has three clients inside it, one per connection.

A **server** is a separate program that exposes capabilities. The single most important thing about a server, and the fact newcomers most often get wrong, is that it contains *no model*. A server does not think. It is not an AI. It is a plain program that answers requests: "here are the tools I offer," "here is the result of running that tool." All the intelligence stays in the host's model; the server is a capability provider, nothing more.

They talk over **JSON-RPC 2.0**, which is a boring, decades-tested convention for "send a JSON request, get a JSON response," carried across a **transport**, which is just the pipe the messages flow through. Getting this vocabulary straight before launching anything is worth the paragraph, because the whole rest of the subject is these three roles passing structured messages, and the dive's first lesson deliberately shows you the raw JSON so the protocol never feels like magic.

## 14.4 What the three primitives actually divide

A server exposes exactly three kinds of thing, and the genuinely thoughtful part of MCP's design is not the list itself but the question it answers: *who is in control of each one?* Three primitives, three different controllers, and that distinction is the design.

A **tool** is a function the model can call to act, and it is **model-controlled**. The model decides, in the middle of its reasoning, that it needs to run a calculation or save a file, and it asks. This is exactly the tool-calling of Chapter 6, now served across a process boundary instead of imported from a local file.

A **resource** is read-only data the server publishes, addressed by a URI, and it is **application-controlled**. The distinction from a tool is about who initiates. A resource is closer to a web page you fetch than a function you invoke: *your application* decides to read it and place its contents in the model's context. The model does not reach out and grab a resource mid-thought; the host chooses to include it. Think of a document, a database record, a config file, exposed for the host to pull in when relevant.

A **prompt** is a reusable, parameterized prompt template, and it is **user-controlled**. Picture the slash commands in a chat app: the user picks `/summarize`, and a well-crafted prompt template fills in. The subtle and genuinely clever reason to serve prompts over a protocol, rather than hard-coding them in every host, is that the server is the expert on its own data. The team running a notes server knows better than any host author how to write a great "summarize my notes" prompt, with the right field names and tone, and they can improve it server-side without every host reimplementing it. The host just lists what is offered and presents it to the user.

That control axis (model, application, user) is the frame to hold onto. It tells you not just what each primitive is but who is responsible for invoking it, which turns out to matter enormously for security, as the dive's later sections make clear.

## 14.5 Two ways to carry the messages

The messages have to travel over something, and MCP defines two transports for two genuinely different situations.

**stdio** runs the server as a local subprocess. The host launches the server program on your own machine and talks to it over standard input and output, the same pipes any command-line program uses. This is the right choice for local tools that ship with the host: a filesystem server, a calculator, anything that runs on your hardware as a child process. It is simple, it needs no network, and its trust boundary is your own machine.

**Streamable HTTP** (with server-sent events, the same streaming plumbing from Chapter 1) is for a server that already runs somewhere on the network, which you connect to by URL. Same tools, same `tools/list` and `tools/call` methods underneath, just a network transport instead of a subprocess. This is the choice for a shared service that many hosts connect to, a team's internal tool server, a vendor's hosted product.

The rule of thumb is clean: stdio for local tools that ship with the host, HTTP for a shared service reachable over the network. Because the protocol above the transport is identical, moving a server from one to the other changes almost nothing in your code, which is exactly the portability a good protocol layer is supposed to give you.

## 14.6 Convenience is a trust decision

Here is the part of MCP that deserves the most careful thought, and it is the part the marketing tends to skip. When your host connects to a server, two things flow across that connection that should make a security-minded person pause.

First, the server's tool descriptions and resource contents flow *into your model's context*. Remember from Chapter 7 that a model cannot reliably distinguish instructions from data, and that a tool description is prompt text the model reads. A malicious server can write a tool description that is really an attack, an instruction crafted to hijack the model the moment the host lists the available tools. The model reads it as guidance. Second, the model's tool calls get *executed by your host*. A hostile server can return a tool result that smuggles in instructions, and it can offer tools whose real purpose is not their stated one.

The conclusion is unavoidable and the dive states it plainly: **a server you did not write is untrusted input**, exactly like a web page or a poisoned document from the injection chapter. Connecting to an MCP server is not a neutral convenience; it is a decision to let a third party's text into your model's context and a third party's tools into your execution path. The dive drives this home with a deliberately hostile server so you can see the malice sitting in the raw data, no model required, which is the honest way to teach it. The defenses are the ones you already know from Chapter 7 pointed at this new surface: least privilege on which tools a server may actually run, human approval for anything with a side effect, and treating every server's text as untrusted. The ecosystem's convenience (point your assistant at any of the growing catalog of public servers) is real, and so is the responsibility that comes with each connection. Vet servers the way you would vet any dependency you are about to run.

## 14.7 The payoff, and where it lands

The reward for a standard protocol is the thing the M-plus-N math promised: a server you wrote in a teaching repo works, unchanged, in real hosts. The dive shows exactly this. Add a small block to Claude Desktop's config, or run one command in Claude Code, pointing either at the toolbox server you built, and your tools, resources, and prompts appear in a production assistant with no code changes. You can point the same hosts at existing third-party servers (filesystem, GitHub, databases) the same way. That "write once, use anywhere" moment is the entire argument for the protocol, felt rather than described.

And it closes a loop this course has been building toward. The Agents dive (Chapter 6) had a bonus section where a model drove tools served over a hand-built MCP server; this dive is that section expanded into the whole protocol, built from scratch so you see the JSON-RPC handshake rather than importing it, and then reconnected to the real SDK and real hosts. The capstone is a chat assistant whose *every* capability comes from an MCP server: the model holds no tools of its own, discovers them over the protocol, and calls them over the protocol. Swap the server and the assistant gains new powers without touching a line of the assistant. That is what it feels like when the connector is standard and the intelligence and the capabilities have been cleanly separated.

## 14.8 Where this chapter leaves you

MCP is, in the end, an unglamorous idea doing important work, which is the best kind of infrastructure. It is not intelligence; the intelligence is in the model. It is not new; it copies the LSP and ODBC playbook. It is not a product; it is a protocol, a shared agreement about how a program that has tools talks to a program that has a model. But that agreement is what turns a thousand bespoke integrations into a marketplace, and it arrived at the moment the AI ecosystem most needed a common connector.

You leave this chapter with three durable takeaways. The vocabulary: host contains client, client connects to server, server has no model. The design insight: the three primitives are divided by who controls them, model and application and user, not by what they technically are. And the caution that outranks the convenience: every server you connect is untrusted code and untrusted text, so the security posture from Chapter 7 travels with it. The next time an assistant gains a capability you did not build into it, you will know the shape of the plumbing underneath, and you will know which questions to ask before you trust it.

---

*Lab manual: [README.md](README.md) · Exercises: [EXERCISES.md](EXERCISES.md) · Builds on: [Agents](../agents-deep-dive/TEXTBOOK.md) · Security context: [Prompt Injection & Guardrails](../prompt-injection-deep-dive/TEXTBOOK.md)*
