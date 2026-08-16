# Frontend and UI Acceptance

Apply this guidance whenever the requested change affects a frontend, browser
flow, visual layout, interaction, or user-facing UI behavior.

- Treat the browser as a required evidence surface, not an optional screenshot
  step. The execution goal must name Chrome `browser_use` (or the available
  equivalent) and the actual route or flow to exercise.
- Verify the user-visible behavior through real interaction: load the target,
  perform the primary actions, check success and failure states, and inspect
  responsive or relevant viewport behavior. Do not substitute unit tests, DOM
  inspection, or a successful build for interaction evidence.
- Record the URL or route, action sequence, observed result, and screenshots or
  equivalent browser evidence. Separate functional acceptance from UI/UX and
  accessibility observations.
- If Chrome, a signed-in session, a running server, or another required runtime
  capability is unavailable, record the exact missing gate as `needs input` and
  continue non-browser work. Do not claim UI acceptance or mark the whole goal
  `blocked` because a browser lane is waiting.
- The final gate requires both application behavior and browser/UI/UX evidence;
  a generated `/goal` or a static render alone is not proof of acceptance.
