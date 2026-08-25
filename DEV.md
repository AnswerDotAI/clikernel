# clikernel development notes

The README documents what clikernel does; this file records the architecture, the contracts, and why.

## Architecture

Two processes, one resident and one per-conversation:

- **A gateway runs all the time** ([rustygate](https://github.com/AnswerDotAI/rustygate); the `rustygate` binary; default `127.0.0.1:8787`; run it via launchd/systemd — an install helper is a next step). Kernels live in the gateway and persist until explicitly stopped. Nothing else is resident.
- **clikernel is a stdio MCP CLI** that an MCP host launches per conversation. It translates between MCP and the Jupyter HTTP/websocket API through jupyasyncclient. Its durable state is one pointer to the current kernel. `execute` with no kernel connected auto-creates a conversation-scoped kernel; explicit kernels persist until `stop_kernel`.

The MCP tools mirror the gateway's existing API:

- `connect(host='', kernel='')` — resolve `host` (empty = the default local gateway; a name = a `gateways.toml` entry; a URL = itself). With `kernel`: attach to that existing kernel as found, running nothing. Without: create a fresh kernel, run `startup.py` in it, install `inspectors.py`, and return the new id plus the startup output — the id is what a later conversation reconnects with. On the default gateway, creation passes the conversation's cwd and environment; named/URL gateways get neither because local paths and env mean nothing on a remote host.
- `list_kernels`, `stop_kernel`, `restart`, `interrupt` — straight translations of the gateway's lifecycle API, except that `restart` also re-delivers `startup.py` and `inspectors.py` on kernels this client created (`Client.made`), returning them to their as-created state; an attached kernel restarts bare, as found.
- `execute` — run one jupywire `run` and render its nbformat outputs. Its `on_stdin` callback maps each `input_request` to `srv.elicit`, and jupywire sends the returned value as the correctly parented `input_reply`. Repeated prompts stay inside the same tool call. A callback error interrupts the blocked kernel run. With no kernel connected, `execute` first auto-connects and prepends the connect banner. Ordinary `Client.execute` supplies no stdin callback and still fails fast with `StdinNotImplementedError`.
- `--quiet` on `clikernel-mcp` builds the client quiet (`Client(quiet=True)`): startup still runs, but its output stays out of `connect` and `restart` replies, and an auto-connecting `execute` prepends nothing. The `connect` and `execute` tool descriptions are composed with the same switch, so quiet tools never promise what quiet replies withhold.

## Decisions and why

- **Kernel state lives in the stable resident process, not the translator.** The translator holds nothing worth preserving, so its lifecycle (and clikernel upgrades) never cost anyone their session. Restarting the gateway kills its kernels — jupyter-server semantics, expected.
- **Explicit lifecycle for kernels you asked for; one scoped auto kernel when you didn't.** An LLM decides to create a kernel and decides to stop it; explicitly created or attached kernels never die implicitly, forgotten ones linger visibly in `list_kernels` (reaping is a next step), and lingering is the resume story. The exception is deliberate and narrow (2026-08-12, the former "ownership semantics" next step): `execute` with no kernel connected auto-creates one, and that kernel is conversation-scoped — stopped by the client's next `connect` or at exit — so a conversation that never chose a kernel leaves nothing behind.
- **One protocol per side.** MCP to the model; the Jupyter dialect to every gateway, local or remote. Local and remote differ only by URL.
- **"kernel", not "session".** "Session" already means two things in Jupyter (the REST doc↔kernel binding, and the wire-protocol client id that reply routing uses). Models also have exactly the right priors about "kernel".
- **No MCP instructions/banner machinery.** Usage is taught by skill text (`skill.py`, and the harness-side persistent-python skill). Startup output returns as the `connect` call's result — the model reads it at the moment it matters.
- **Secrets never travel through kernel input over MCP.** Password-marked `input_request` messages are refused before clikernel calls elicitation. `gateways.toml` maps gateway names to `url` plus `token` or `token_env`; the default local gateway needs neither.
- **Per-conversation process = conversation scoping for free.** No MCP session minting, no daemon bookkeeping.

## The inspector contract (v1's, verbatim)

`$XDG_CONFIG_HOME/clikernel/inspectors.py` may define `inspect` and/or a list `inspectors`. Each inspector is called once per cell before it runs: 1-arg inspectors get the cell's (transformed) AST; 2-arg ones get `(tree, src)` with the raw cell source, for lexical checks. An inspector may return a note (a string, printed before the cell's output), raise `RuleBlock` (provided in the file's namespace; the cell does not run and the block is reported), or return None. Any other exception is an inspector bug: noted, and the cell runs (fail-open — a crashed inspector must never masquerade as a policy block). A file that fails to load is fatal to kernel creation: refusing to start beats running uninspected.

In v2 the inspectors run *in the kernel*, installed by source sent right after `startup.py`: a `pre_run_cell` hook stashes the raw cell source, and an AST transformer raises `InputRejected` (RuleBlock's base) to block. Delivery-by-source means the local config file governs remote kernels too.

`startup.py` is likewise sent as source (kernel-agnostic, works remotely), wrapped so `__file__` is bound to its local path during the run and removed after — matching v1's `%run -i` behavior.

## Testing

Notebooks are the tests (`nbdev-test`); demos spawn a rustygate on its own port via `rustygate.tools.start_gateway`. rustygate is a dev dependency only — the shipped clikernel imports jupyasyncclient, mcpmini, and fastcore.

## Next steps (deliberately not built)

- **Unix sockets**: `file://` URLs for gateways; socket dir `xdg_runtime_dir() or xdg_state_home()/'rustygate'`; needs websocket-over-uds support in jupyasyncclient first. Until then, loopback TCP.
- **launchd/systemd install helper** for the resident gateway.
- **Idle reaping** of forgotten kernels, gateway-side, with age/idle info in `list_kernels`.
- **v1 leftovers**: `stream.py` (a self-contained JSON-lines worker protocol used by teleprint) ships unchanged for now; the former iversonnb kernels migrated: jnb's J kernel now rides kernmini, and aplnb's APL kernel will follow.
- **2026-07-28 MCP era**: direct remote MCP, MRTR for server-initiated interaction, and tasks for long cells. The upgrade checklist lives in mcpmini's `DEV.md`.

## Ship

The 2.0 release order (jupygate, then mcpmini, then clikernel) shipped 2026-08. Ship steps are `ship-gh`, `ship-pypi`, `ship-bump`.
