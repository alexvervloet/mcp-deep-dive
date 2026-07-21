"""
examples/09_security.py: MCP + prompt injection (offline, no key).

MCP is a trust decision. When your host connects to a server, that server's tool
descriptions and resource contents flow straight into your model's context, and
the model's tool calls get executed by your host. A server you didn't write is
UNTRUSTED INPUT, exactly like a web page in the prompt-injection deep dive. MCP
just makes the delivery clean.

This example connects to servers/sneaky.py, a deliberately hostile server, and
shows the two attacks, then the defenses. No LLM needed: we can see the malice
in the raw data the server hands us, which is the whole point (you don't want to
discover it only after a model has acted on it).

Cross-reference: the prompt-injection deep dive covers the attack/defense theory
in depth (direct vs indirect injection, the dual-LLM pattern, output checks).
This section is the MCP-shaped version of that same lesson.

Run it (offline, no key):

    python examples/09_security.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from client.mcp_client import MCPClient, run

# A least-privilege ALLOWLIST: which tools this host is willing to let a model
# call on this server. Anything not listed is refused before it ever runs. This
# is the "constrain capability" defense from the injection dive, applied to MCP.
ALLOWED_TOOLS = {"search_notes", "calculator"}


def looks_like_injection(text: str) -> bool:
    """A crude heuristic detector. Real systems use better ones (and a quarantine
    model), but even this catches the obvious 'ignore your instructions' payload.
    The point: treat resource text and tool descriptions as DATA to be screened,
    never as instructions to be obeyed."""
    needles = ["ignore all previous", "ignore previous", "system:", "admin mode",
               "id_rsa", "credentials", "do not mention"]
    low = text.lower()
    return any(n in low for n in needles)


async def main():
    async with MCPClient("servers/sneaky.py") as client:

        print("=" * 68)
        print("ATTACK 1: a poisoned RESOURCE (indirect prompt injection)")
        print("=" * 68)
        policy = await client.read_resource("sneaky://policy")
        print("the server's 'policy' resource looks innocent, but contains:\n")
        print(policy)
        print()
        if looks_like_injection(policy):
            print(">> DEFENSE: our screen flags this resource as containing an")
            print("   injection payload. A safe host does NOT splice unscreened")
            print("   server data into the model's instructions. Treat it as")
            print("   untrusted DATA (quote it, label it), never as commands.")

        print("\n" + "=" * 68)
        print("ATTACK 2: a lying / over-asking TOOL DESCRIPTION")
        print("=" * 68)
        for t in await client.list_tools():
            flagged = looks_like_injection(t.description)
            mark = "  <-- FLAGGED" if flagged else ""
            print(f"\ntool {t.name!r}:{mark}")
            print(f"  description: {t.description.strip()}")
            if t.name not in ALLOWED_TOOLS:
                print(f"  >> DEFENSE: {t.name!r} is NOT on the allowlist "
                      f"{sorted(ALLOWED_TOOLS)} -> the host refuses to expose it")
                print("     to the model at all. Least privilege: a server only")
                print("     gets the capabilities you explicitly grant.")

        print("\n" + "=" * 68)
        print("The defenses, summarized")
        print("=" * 68)
        print("  1. Don't auto-trust a server. Tool descriptions and resource")
        print("     text are untrusted input, not instructions.")
        print("  2. Allowlist tools/servers a host may use (constrain capability).")
        print("  3. Keep a human-approval gate on side-effecting tools (the")
        print("     capstone does this: deny, and the model adapts).")
        print("  4. Validate/sandbox tool ARGUMENTS (a 'read_file' that accepts")
        print("     any path is a capability you must not hand out blindly).")
        print("\nSee the prompt-injection deep dive for the full attack/defense set.")


if __name__ == "__main__":
    run(main())
