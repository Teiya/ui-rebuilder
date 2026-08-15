# Public repository checklist

## Repository boundary

Commit the UI Rebuilder source, schemas, synthetic tests, lock manifests, documentation, and reviewed compatibility patches. Do not commit:

- `third_party/open-pencil`, `third_party/comfyui`, custom-node checkouts, or virtual environments;
- model weights, fonts, private screenshots, generated packages, API keys, cookies, or local absolute paths;
- consumer-specific reconstruction jobs, art direction, or game assets unless that consumer explicitly publishes them under a compatible license.

The repository is deliberately not implemented as a collection of Git submodules. A lock manifest plus bootstrap script gives a single reproducible install command, supports profile-based installation, and keeps upstream license boundaries visible.

## Before the first GitHub push

1. Confirm the root MIT `LICENSE` still matches the intended UI Rebuilder copyright holder. OpenPencil and other third-party licenses remain independent.
2. Replace repository placeholders in `pyproject.toml` after the final GitHub owner/repository name is known.
3. Run `python scripts/bootstrap.py --profile fig`, unit tests, `ui-rebuilder doctor`, and a synthetic or redistributable full `.fig` example.
4. Run a secret scanner and inspect `git status`, including the initial commit, for private paths and binary assets.
5. Enable branch protection, dependency updates, and required CI checks on GitHub.

## Updating a downloaded tool

1. Change only the immutable revision in `third_party/tools.lock.json`.
2. Review upstream license and security changes.
3. Rebase or remove local patches; never silently edit downloaded source and rely on an unrecorded dirty checkout.
4. Rebuild and run the full five-page `.fig` acceptance package.
5. Record model filename/hash changes separately in `models.lock.json`.

## Release semantics

`complete-fig-pending-visual-approval` means the `.fig` package is structurally complete. It does not mean third-party model output, consumer artwork, accessibility exceptions, or visual similarity have been legally or artistically approved.
