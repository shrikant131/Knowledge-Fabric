# Upload to GitHub

This repository is prepared for manual GitHub upload.

## Option 1 — GitHub web upload

1. Create a new empty repository on GitHub.
2. Do not add a README, license, or `.gitignore` during creation because this repository already contains them.
3. Upload the repository contents.
4. Commit to the default branch.

## Option 2 — Git CLI

From this directory:

```bash
git init
git add .
git status
git commit -m "Initial Knowledge Fabric product"
git branch -M main
git remote add origin <YOUR_GITHUB_REPOSITORY_URL>
git push -u origin main
```

Before pushing, verify:

```bash
python scripts/repo_check.py
```

## Recommended repository settings

After creating the repository:

- Enable branch protection for `main`.
- Require CI to pass before merging.
- Enable Dependabot/security alerts where available.
- Add a repository description.
- Add the appropriate open-source or internal license.
- Keep production secrets in GitHub Actions Secrets / cloud secret management, never in files.
