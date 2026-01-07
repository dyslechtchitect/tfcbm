# TFCBM CI/CD Configuration

This directory contains the GitHub Actions workflows for TFCBM.

## Workflows

### `flatpak-ci.yml` - Main CI Pipeline

Runs on every push to `main`/`develop` and on pull requests.

**Jobs:**

1. **test** - Runs unit tests
   - Python tests (pytest)
   - Node.js tests (npm test)
   - Runs first to fail fast if tests don't pass

2. **flatpak** - Builds Flatpak packages
   - Matrix builds for GNOME versions: 48, 49
   - Uses official Flatpak GitHub Actions
   - Uploads artifacts for each version
   - Only runs if tests pass

3. **lint** - Lints Flatpak configuration
   - Runs `flatpak-builder-lint` on manifest
   - Builds a repo and lints it
   - Checks for common packaging issues

**Artifacts:**

Flatpak bundles are uploaded for each GNOME version and retained for 7 days:
- `tfcbm-gnome48-flatpak`
- `tfcbm-gnome49-flatpak`

## Running Locally

You can run the CI workflow locally using `act`:

**Quick start:**
```bash
# Run tests
./run-ci-locally.sh test

# Build for GNOME 49
./run-ci-locally.sh flatpak 49

# Build for all GNOME versions
./run-ci-locally.sh flatpak-all

# Run linting
./run-ci-locally.sh lint

# Run everything
./run-ci-locally.sh all
```

For detailed instructions, see [LOCAL_TESTING.md](workflows/LOCAL_TESTING.md).

## Supported GNOME Versions

The extension and app are tested against:
- GNOME 49 (org.gnome.Platform 49)

**Note:** GNOME 45 and 46 reached End-of-Life in April 2025 and are no longer supported.

The Flathub submission uses GNOME 49 as the primary runtime version.

## CI Status

The CI workflow will:
- ✅ Pass if all tests pass and Flatpak builds successfully
- ⚠️ Warn if tests fail but continue building (during development)
- ❌ Fail if Flatpak build fails

## Adding New Workflows

To add a new workflow:

1. Create a new `.yml` file in `.github/workflows/`
2. Define the workflow name, triggers, and jobs
3. Test locally with `act -W .github/workflows/your-workflow.yml`
4. Commit and push

## Troubleshooting

### Workflow not triggering

Check:
- Workflow file is in `.github/workflows/`
- File has `.yml` or `.yaml` extension
- Syntax is valid (use `actionlint` to check)
- Triggers are configured correctly

### Build failures

1. Check the job logs in GitHub Actions
2. Reproduce locally: `./run-ci-locally.sh all`
3. Fix issues and test again
4. Push changes

### Permission errors

Workflows run with default `GITHUB_TOKEN` permissions. If you need additional permissions, update the workflow:

```yaml
permissions:
  contents: read
  packages: write
```

## Further Reading

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Flatpak GitHub Actions](https://github.com/flatpak/flatpak-github-actions)
- [act - Run GitHub Actions locally](https://github.com/nektos/act)
- [actionlint - Workflow linter](https://github.com/rhysd/actionlint)
