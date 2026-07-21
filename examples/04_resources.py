"""
examples/04_resources.py: RESOURCES: read-only data for the model (offline).

A tool is something the model *calls* to act. A RESOURCE is read-only DATA the
server publishes by URI, closer to a GET endpoint than a function call. The
distinction is about control: your *application* decides to read a resource and
put its contents into the model's context; the model doesn't invoke it the way
it invokes a tool.

The notes server (servers/notes.py) exposes two:
  - notes://all          a static resource: a directory of all notes
  - notes://note/{key}   a TEMPLATED resource: one note, addressed by key

This example connects, lists the static resources, then reads a few by URI 
again with no LLM. (In Section 8 the host will read a resource and hand its text
to the model as context; here we just see the data come back over the wire.)

Run it (offline, no key):

    python examples/04_resources.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from client.mcp_client import MCPClient, run


async def main():
    async with MCPClient("servers/notes.py") as client:

        # List the server's STATIC resources (resources/list). Templated ones
        # like notes://note/{key} are listed separately by the protocol
        # (resource *templates*); you read them by filling in the {key}.
        print("static resources the server publishes:")
        for uri, name in await client.list_resources():
            print(f"  - {uri}  ({name})")

        # Read the directory resource (resources/read).
        print("\nread notes://all:")
        print(await client.read_resource("notes://all"))

        # Read individual notes via the templated URI: fill in {key}.
        print("\nread a couple of templated resources:")
        for key in ["plans", "offline"]:
            text = await client.read_resource(f"notes://note/{key}")
            print(f"  notes://note/{key} -> {text}")

    print("\nKey idea: resources are DATA, fetched by the app, not 'called' by")
    print("the model. Same connection, same JSON-RPC, different primitive.")


if __name__ == "__main__":
    run(main())
