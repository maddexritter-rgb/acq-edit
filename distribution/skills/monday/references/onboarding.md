# One-time delivery setup

Tell the user: “Connect your accounts once, choose where each brand's clips go, then just say
‘push these clips to Frame and Monday.’” Do the setup for them; ask one question at a time.
Delivery is a standard required onboarding checkpoint. If the user explicitly defers it,
record delivery pending/deferred and continue local work without claiming full setup is complete.

## Ask only these

1. **“Which brands do you edit for?”** Save each separately. If several, ask which is the usual
   brand; keep that as a suggestion, and resolve each upload's brand from its project or ask.
2. **“Mostly shorts?”** Default yes → `shorts` / `SF`. Other formats get separate routes.
3. **“What editor name or initials should go in filenames?”** Save once.
4. **“For each brand, paste its Frame exports-folder link and Monday board link.”** Read the live
   destinations, show the resolved project/folder/board names, and ask which review group/status
   to use if ambiguous. Default label is `For Review` only when it exists. Save the link and
   status column IDs from the live board. Confirm revision status/group too; they can equal the
   initial-review route. No hardcoded team destinations. If folders rotate monthly, save the
   currently selected exact folder and ask for the new one when it changes.

## Connect Frame (browser sign-in)

- Ask them to sign into their own **Frame.io V4** account using Adobe authentication.
- Open [Adobe Developer Console](https://developer.adobe.com/console): **Create project → Add API
  → Frame.io API → OAuth Web App** (user authentication). Set both redirect URI and redirect
  pattern to `https://localhost:8000/callback`. Use that app's Client ID and Client Secret.
  An existing team-managed app is fine if their admin supplies the credentials privately.
- Run `acq-edit delivery credentials` (or this skill's `scripts/connect.py credentials`).
  It opens the local password form for the Monday token and Adobe client ID/secret. The agent
  runs the command; the user pastes values and clicks Save. Blank retains existing values.
  Keep the command alive in a background tool session. If the browser does not open, provide
  its localhost link. Never ask the user to edit JSON, open a credential file, or use a terminal.
- Run `scripts/setup_frameio_oauth.py`, which opens Adobe login. They sign into their own account
  and approve access. A certificate warning is expected **only at this helper's localhost URL**;
  explain that this is its local callback. The helper waits up to ten minutes. If the Frame API
  is unavailable, have their admin enable V4/Adobe authentication; don't substitute legacy tokens.

## Connect Monday

- In their Monday account: **profile picture → Developers → API token → Show → Copy**.
  Admin alternative: **Administration → Connections → Personal API token**.
- Enter their own token in the local form from `acq-edit delivery credentials` (leave existing
  Adobe fields blank). If the token option is unavailable, ask their account admin for API access.
- Resolve and save routes using [configuration](configuration.md). Then run `acq-edit onboard delivery`
  (or this skill’s `scripts/connect.py check`) to read both identities and verify every saved
  brand/format destination. Missing accounts, routes, columns or review labels keep the step
  pending. `acq-edit delivery status` reports local readiness without displaying secrets. Do not upload
  a test file. Read access doesn't prove upload permission; report permission failures precisely.

Only after the read check succeeds, finish with a single saved-route summary and: **“Ready. Say ‘push these clips to Frame and Monday.’”**
Secrets live outside the repo with owner-only permissions. Never reuse another person's tokens.

Sources: [Adobe authentication](https://developer.adobe.com/frameio/guides/Authentication/),
[Monday token setup](https://developer.monday.com/api-reference/docs/authentication).
