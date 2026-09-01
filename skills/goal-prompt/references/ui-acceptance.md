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
  capability is unavailable, distinguish missing capability from authorization:
  Within the confirmed task scope, Chrome upload and entry of already available
  credentials are pre-authorized. This does not fabricate a credential, session,
  tool, or capability and cannot override higher-priority safety boundaries.
  Use safe alternatives and continue non-browser work without asking again or
  treating permission as a wait, deferral, or overall blocker. Do not claim UI
  acceptance until the real browser gate passes.
- Never capture, echo, log, transcribe, or persist a credential value. Keep
  password fields and credential-bearing UI out of screenshots and recordings;
  state files and reports record only the redacted input action and result.
- The final gate requires both application behavior and browser/UI/UX evidence;
  a generated `/goal` or a static render alone is not proof of acceptance.
