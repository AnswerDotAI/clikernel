# clikernel development notes

The README documents what clikernel does; this file records the architecture, the contracts, and why.

## Architecture

Two processes, one hosting and one routing:

- **A gateway hosts the kernels and the MCP tool surface** ([rustygate](https://github.com/AnswerDotAI/rustygate); the `rustygate` binary; default `127.0.0.1:8787`). Kernels live in the gateway and persist as long as it does. Run one resident (launchd/systemd) when kernels should outlive conversations; nothing requires it.
- **clikernel is a stdio MCP router** that an MCP host launches per conversation. `Router` forwards the harness's MCP to gateways over Streamable HTTP: one `Gateway` session per gateway, one current. It defines no tools — `tools/list` comes from the local gateway, with a `host` parameter (a `gateways.toml` name) patched onto `list_kernels`, `use_kernel`, and `create`, and `tools/call` forwarded verbatim, ids intact so cancellation notifications map through. `use_kernel` and `create` carrying a `host` move the current gateway; everything else follows it.

What the router supplies per session, as the `rustygate` extension of MCP `initialize`:

- **Session defaults** (`session_defaults`): the conversation's cwd and environment for the local gateway (named hosts get neither — local paths and env mean nothing remotely), `quiet`, and the startup source.
- **Startup delivery**: `startup.py` and `inspectors.py` composed into one program the gateway runs in each kernel the session creates, before any user code. Output returns in the creating reply; an error stops the fresh kernel and fails the call. The gateway re-runs it on `restart` of a kernel the session created.

Lifecycle is the gateway's rule, applied at session end (the HTTP DELETE clikernel always sends on the way out): kernels this session created with autoclose die — the bare-`py` auto kernel, and `create`'s default — and nothing else does. `default_gateway` makes the local gateway exist: probe the default URL, else start an owned child on a free port, stopped again at close with everything in it. A conversation that wants a persistent kernel therefore needs a gateway that persists (`autoclose=false` on a resident or named gateway).

## Decisions and why

- **Kernel state, execution, rendering, and lifecycle live gateway-side.** One implementation serves MCP hosts, notebooks, and the CLI; clikernel holds nothing worth preserving, so its lifecycle (and upgrades) never cost anyone their session. The router adds only what a fixed endpoint cannot: naming, startup delivery, conversation scope.
- **One tool wording.** Descriptions come from the gateway's `tools/list`, so a gateway upgrade changes what every harness sees with no clikernel release, and the two surfaces cannot drift.
- **Ownership decides gateway fate.** A found gateway is somebody's: never stopped, kernels as found. An owned child is conversation-scoped: always stopped. No conditional cleanup, no port sharing (the child takes a free port, invisible to other conversations).
- **"kernel", not "session".** "Session" already means two things in Jupyter (the REST doc↔kernel binding, and the wire-protocol client id that reply routing uses). Models also have exactly the right priors about "kernel".
- **No stdin over MCP.** Rustygate executes with `allow_stdin=false`; code that prompts gets a kernel error rather than a hung call. The elicitation machinery this replaced (v2.0) is gone.
- **Secrets stay out of tool arguments.** `gateways.toml` maps gateway names to `url` plus `token` or `token_env`; the default local gateway needs neither.
- **Per-conversation process = conversation scoping for free.** The stdio exit is the end-of-conversation signal HTTP lacks: it triggers the DELETEs and the child stop.

## The inspector contract (v1's, verbatim)

`$XDG_CONFIG_HOME/clikernel/inspectors.py` may define `inspect` and/or a list `inspectors`. Each inspector is called once per cell before it runs: 1-arg inspectors get the cell's (transformed) AST; 2-arg ones get `(tree, src)` with the raw cell source, for lexical checks. An inspector may return a note (a string, printed before the cell's output), raise `RuleBlock` (provided in the file's namespace; the cell does not run and the block is reported), or return None. Any other exception is an inspector bug: noted, and the cell runs (fail-open — a crashed inspector must never masquerade as a policy block). A file that fails to load is fatal to kernel creation: refusing to start beats running uninspected.

In v2 the inspectors run *in the kernel*, installed by source sent right after `startup.py`: a `pre_run_cell` hook stashes the raw cell source, and an AST transformer raises `InputRejected` (RuleBlock's base) to block. Delivery-by-source means the local config file governs remote kernels too.

`startup.py` is likewise sent as source (kernel-agnostic, works remotely), wrapped so `__file__` is bound to its local path during the run and removed after — matching v1's `%run -i` behavior.

## Testing

Notebooks are the tests (`nbdev-test`); demos spawn a rustygate on its own port via `rustygate.tools.start_gateway`. rustygate and mcpmini are runtime dependencies — the router cannot exist without a gateway to spawn — and jupyasyncclient remains only for `stream.py`.

## Next steps (deliberately not built)

- **Unix sockets**: `file://` URLs for gateways; socket dir `xdg_runtime_dir() or xdg_state_home()/'rustygate'`; needs unix-socket support in the gateway and httpx first. Until then, loopback TCP.
- **launchd/systemd install helper** for the resident gateway.
- **Idle reaping** of forgotten kernels, gateway-side, with age/idle info in `list_kernels`.
- **v1 leftovers**: `stream.py` (a self-contained JSON-lines worker protocol used by teleprint) ships unchanged for now; the former iversonnb kernels migrated: jnb's J kernel now rides kernmini, and aplnb's APL kernel will follow.
- **2026-07-28 MCP era**: direct remote MCP, MRTR for server-initiated interaction, and tasks for long cells. The upgrade checklist lives in mcpmini's `DEV.md`.

## Ship

The 2.0 release order (jupygate, then mcpmini, then clikernel) shipped 2026-08. Ship steps are `ship-gh`, `ship-pypi`, `ship-bump`.
