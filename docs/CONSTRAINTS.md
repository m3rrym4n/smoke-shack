# smoke-stack hard constraints (read before every job)

This file supplements `docs/SPEC.md`. If the two disagree, this file wins.

## 1. Never talk to the grill directly

The grill's WiFi module serves a **serial UDP stream** (port 8080) and supports **one UDP client at a time**. Home Assistant's `gmg-ha` integration (PyPI library `gmg-local`) is that one client. A second client makes the grill return truncated or garbage replies for everyone (seen on the first real cook: setpoint 0 / 65535, mode flipping to off, warning "Unknown", probes flapping).

Rules for ALL code in this repo:
- smoke-stack must NEVER open a UDP socket to the grill, import `gmg-local`, or poll the grill's IP in any way. This includes scripts, tests that hit real hardware, and "discovery" helpers.
- All grill data comes from Home Assistant (websocket `state_changed` events and `get_states`).
- All grill control (Start, Fan, Shutdown, setpoint, profile steps) goes through Home Assistant services (`climate.set_hvac_mode`, `climate.set_temperature`), never direct UDP.
- Do not add dependencies such as `gmg-local`, or any code that uses `socket` for the grill.

## 2. Treat grill data as untrusted

Even through HA, the integration can pass through garbage when the grill's reply is malformed. Ingest must validate snapshots (plausible setpoint, temperatures, known states) and ignore implausible ones instead of recording them or changing a cook's phase (see issue #32).

## 3. Other clients on the network

Anything else that talks to the grill (the GMG phone app, other tools) can corrupt the stream too. Do not try to fix that in code; document it and let the owner remove the other clients.
