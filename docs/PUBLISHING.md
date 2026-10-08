# Manual GitHub publication

The prepared repository is local only, on branch `main`. It has no GitHub remote.

1. Review `LICENSE`, `README.md`, and every tracked file. Confirm the public repo
   name and license suit your project.
2. Run checks:

   ```sh
   python3 -m unittest discover -v
   python3 scripts/audit_release.py
   git status --short
   git log --oneline
   git ls-files
   ```

3. Create a new empty GitHub repository (for example `mini-agent-connector`).
   Do not initialize it with another README, license, or .gitignore.
4. From this local checkout, substitute your actual owner/repository:

   ```sh
   git remote add origin git@github.com:YOUR_ACCOUNT/mini-agent-connector.git
   git push -u origin main
   ```

5. Verify GitHub Actions completes; enable private vulnerability reporting if
   desired. Link the setup guide in the repository description.

Do not force-add ignored configuration/runtime files. This repository has a fresh
history; do not replace it with a copy of a private workspace repository. You can
change the local license or project name before the first public push.
