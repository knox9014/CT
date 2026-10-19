# Public artifact policy

The repository contains project source, synthetic tests and deliberately reviewed technical evidence. Personal recordings/documents, account state, secrets, raw logs, caches and generated binaries belong in ignored local directories.

- `.gitignore` excludes local/private inputs, credentials, recordings/documents, raw logs and build outputs.
- `python scripts/check_public_artifacts.py --tracked --identity` checks indexed content and the configured commit email.
- Pre-commit checks staged Git blobs rather than potentially different worktree files.
- Pre-push checks every outgoing commit snapshot, including content deleted in later commits, and author/committer email metadata. Reports contain file location and reason only, never matched sensitive content.
- Automatic publishing is restricted to branch commits. Tags and other object types are blocked pending explicit message/tagger metadata review; peeling a tag to a commit is not treated as a full privacy check.
- The only reviewed binary exception is the synthetic vector-add SPIR-V fixture at its recorded hash. New or changed binary artifacts require manual review.
- The local Git identity currently uses the public repository account alias and GitHub noreply email. Existing history was checked without printing the address and contains only that public alias and noreply email.

Enable the committed repository-local hooks with `git config --local core.hooksPath .githooks`. This affects only this checkout, not other repositories. On a new clone the hooks must be enabled again. Hooks can be bypassed by Git options, so the full revision scan is also run explicitly before publication.

Pattern checks are a practical guard, not proof that arbitrary content is free of personal information. Public summaries use synthetic inputs and minimal technical properties; machine-local reports stay in `results/local/`. No raw personal data is needed for CT validation.
