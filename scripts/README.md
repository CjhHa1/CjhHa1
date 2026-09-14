# Profile statistics

The workflow generates four self-contained SVG cards in `assets/` and a public-data snapshot in `assets/profile-data.json`. The README chooses a light or dark card using `<picture>`. No external image renderer or Python packages are required.

## Metrics

- **Public repos:** all public repositories owned by the profile, including forks.
- **Stars earned:** stars on owned public non-fork repositories.
- **Followers:** the public follower count.
- **Public PRs authored:** all public pull requests authored by the user, across repositories and states, from GitHub issue search.
- **Open source contributions:** all-time merged public PRs authored by the user in repositories owned by other accounts. Counts distinct projects and lists the top five by merged PR count, breaking ties alphabetically. Own repositories are excluded case-insensitively; organization-owned repositories are included.
- **Project links:** `assets/contributions.md` links every contributed project and its matching merged PRs. It updates alongside the cards.

Archived repositories are included. Private repositories and private contributions are excluded. Both repository and contribution searches paginate. Incomplete results, inconsistent pages, or GitHub's 1,000-result search cap fail the run instead of publishing partial counts. If contributions exceed that cap, the query must be partitioned before updating again.


## Automatic updates

After pushing to GitHub, open **Actions → Update profile statistics → Run workflow** to refresh manually. The workflow also runs when its source changes on `main`, and is scheduled daily at 00:23 UTC (08:23 China Standard Time). GitHub may delay scheduled runs or disable schedules in inactive public repositories.

The workflow uses its built-in `GITHUB_TOKEN` with `contents: write`; no personal token is needed. Repository or organization policies must allow Actions and writes to the default branch. A protected branch may reject the generated commit; in that case, publish updates through the repository's approved pull-request process. No rules are bypassed by this workflow.

Failed API calls stop generation and leave the previously committed cards visible. Check the Actions log and rerun after resolving an error. Only public aggregate data is saved; credentials are never written to the snapshot or cards.

## Local use

Requires Python 3.9+ and an authenticated GitHub CLI (`gh auth login`).

```sh
python3 -m unittest discover -s tests -v
python3 scripts/generate_stats.py --username CjhHa1
```

Re-render the saved snapshot offline:

```sh
python3 scripts/generate_stats.py --from-json assets/profile-data.json
```

The generator runs `gh api`, which uses `GH_TOKEN` in Actions and your existing GitHub CLI authentication locally.
