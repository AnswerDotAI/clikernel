# clikernel development notes

The README documents what clikernel does; this file records the architecture, the contracts, and why.

## Architecture

Two processes, one hosting and one routing:

- **A gateway hosts the kernels and the MCP tool surface** ([rustygate](https://github.com/AnswerDotAI/rustygate); the `rustygate` binary; default `127.0.0.1:8787`). Kernels live in the gateway and persist as long as it does. Run one resident (launchd/systemd) when kernels should outlive conversations; nothing requires it.
- **clikernel is a stdio MCP router** that an MCP host launches per conversation. `Router` forwards the harness's MCP to gateways over Streamable HTTP: one `Gateway` session per gateway, one current. It defines no tools — `tools/list` comes from the local gateway, with a `host` parameter (a `gateways.toml` name) patched onto `list_kernels`, `use_kernel`, and `create`, and `tools/call` forwarded verbatim, ids intact so cancellation notifications map through. The one exception is `exec`, which must first pass the cell rules. `use_kernel` and `create` carrying a `host` move the current gateway; everything else follows it.

What the router supplies per session, as the `rustygate` extension of MCP `initialize`:

- **Session defaults** (`session_defaults`): the conversation's cwd and environment for the local gateway (named hosts get neither — local paths and env mean nothing remotely), `quiet`, and the startup source.
- **Startup delivery**: Python defaults and `startup.py` composed into one program the gateway runs in each Python kernel the session creates, before any user code. The default is `ast_node_interactivity='all'`; user startup can override it. Output returns in the creating reply; an error stops the fresh kernel and fails the call. The gateway re-runs it on `restart` of a Python kernel the session created. It never runs this program in Luau.

Lifecycle is the gateway's rule, applied at session end (the HTTP DELETE clikernel always sends on the way out). The gateway stops kernels this session created with autoclose, enabled by default. It does not stop kernels merely selected, reused, or created with `autoclose=false`. `default_gateway` makes the local gateway exist: probe the default URL, else start an owned child on a free port, stopped again at close with everything in it. A conversation that wants a persistent kernel needs a gateway that persists (`autoclose=false` on a resident or named gateway).

## Decisions and why

- **Kernel selection and execution are separate.** Rustygate defines `create(kernel?, dlgname?, autoclose?)` and `exec(code, dlgname?)`. The router forwards them unchanged. A new kernel requires an explicit implementation (`luau`, or an installed kernelspec such as `py` or `apl`). Omit `kernel` only to reuse an existing binding. An explicit implementation must match that binding. Creation and selection return usage guidance. Execution requires a selected kernel or an existing dialog binding and never creates or switches kernels. Named hosts use the same rules. The CLI creates `py` explicitly unless `--kernel` selects an existing kernel. Its stream protocol is unchanged.

- **Kernel state, execution, rendering, and lifecycle live gateway-side.** One implementation serves MCP hosts, notebooks, and the CLI; clikernel holds nothing worth preserving, so its lifecycle (and upgrades) never cost anyone their session. The router adds only what a fixed endpoint cannot: naming, startup delivery, conversation scope.
- **One tool wording.** Descriptions come from the gateway's `tools/list`, so a gateway upgrade changes what every harness sees with no clikernel release, and the two surfaces cannot drift.
- **Ownership decides gateway fate.** A found gateway is somebody's: never stopped, kernels as found. An owned child is conversation-scoped: always stopped. No conditional cleanup, no port sharing (the child takes a free port, invisible to other conversations).
- **"kernel", not "session".** "Session" already means two things in Jupyter (the REST doc↔kernel binding, and the wire-protocol client id that reply routing uses). Models also have exactly the right priors about "kernel".
- **No stdin over MCP.** Rustygate executes with `allow_stdin=false`; code that prompts gets a kernel error rather than a hung call. The elicitation machinery this replaced (v2.0) is gone.
- **Secrets stay out of tool arguments.** `gateways.toml` maps gateway names to `url` plus `token` or `token_env`; the default local gateway needs neither.
- **Per-conversation process = conversation scoping for free.** The stdio exit is the end-of-conversation signal HTTP lacks: it triggers the DELETEs and the child stop.

## Startup source

`startup.py` is sent as source (kernel-agnostic, works remotely), wrapped so `__file__` is bound to its local path during the run and removed after — matching v1's `%run -i` behavior.

## Cell rules

`clikernel.rules` checks each `exec` cell in the router, before forwarding it. A note goes in a text block before the gateway's reply, and `--quiet` drops the notes. A blocking rule returns an error result, and the cell never reaches a gateway. Because the rules run in the router, nothing is installed in kernels, remote gateways get the same checks, and there is no plugin interface. They replaced v2's inspectors, which ran a user `inspectors.py` inside every Python kernel.

The rules exist because we measured the difference against prose instructions. Standing instructions such as "always read docs first" hold for a few turns, then lose to task focus. A note that arrives in the tool result, at the moment of the mistake, gets acted on essentially every time, including mid-task where prompt text is weakest. Prohibitions with bright-line triggers bind well in prose. Anything stateful or conditional has to live in the harness, because models don't reliably track state across a long context.

The router can't see which kernel will run a cell. So a rule may only match Python forms that no other kernel language produces. IPython's `!` escape fails that test: APL's `!5` (factorial) transforms into the same `get_ipython().system(...)` call. That is why `!` lines aren't blocked, and neither is Luau's `io.popen`. For the same reason, rules read only the cell's text. A rule that consulted installed packages would check the router's environment, not the kernel's.

The stream CLI talks to gateways directly, so its cells get no rule checks.

## Testing

Notebooks are the tests (`nbdev-test`), except that the rules' parsing edge cases are pytest checks in `tests/test_rules.py`; demos spawn a rustygate on its own port via `rustygate.tools.start_gateway`. rustygate and mcpmini are runtime dependencies — the router cannot exist without a gateway to spawn — and jupyasyncclient remains only for `stream.py`.

## Next steps (deliberately not built)

- **Unix sockets**: `file://` URLs for gateways; socket dir `xdg_runtime_dir() or xdg_state_home()/'rustygate'`; needs unix-socket support in the gateway and httpx first. Until then, loopback TCP.
- **launchd/systemd install helper** for the resident gateway.
- **Idle reaping** of forgotten kernels, gateway-side, with age/idle info in `list_kernels`.
- **v1 leftovers**: `stream.py` (a self-contained JSON-lines worker protocol used by teleprint) ships unchanged for now; the former iversonnb kernels migrated: jnb's J kernel now rides kernmini, and aplnb's APL kernel will follow.
- **2026-07-28 MCP era**: direct remote MCP, MRTR for server-initiated interaction, and tasks for long cells. The upgrade checklist lives in mcpmini's `DEV.md`.

## Ship

The 2.0 release order (jupygate, then mcpmini, then clikernel) shipped 2026-08. Ship steps are `ship-gh`, `ship-pypi`, `ship-bump`.
