# Running GitHub Actions Locally

This guide explains how to run the Flatpak CI workflow locally before pushing to GitHub.

## Prerequisites

### Install `act`

`act` allows you to run GitHub Actions locally using Docker.

**IMPORTANT:** Do NOT use `dnf install act` on Fedora/RHEL as it installs the wrong package (Automatic Component Toolkit). Use one of the methods below instead.

**Recommended installation (Linux):**
```bash
curl -s https://raw.githubusercontent.com/nektos/act/master/install.sh | sudo bash
```

**On Ubuntu/Debian:**
```bash
curl https://raw.githubusercontent.com/nektos/act/master/install.sh | sudo bash
```

**Using Homebrew (macOS/Linux):**
```bash
brew install act
```

### Install Docker

`act` uses Docker to run the workflows.

**On Fedora:**
```bash
sudo dnf install docker
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker $USER
```

Then log out and back in for group changes to take effect.

## Quick Start

### Run all jobs locally:

```bash
act -j test -j flatpak -j lint
```

### Run specific jobs:

**Run only tests:**
```bash
act -j test
```

**Run only Flatpak build for GNOME 49:**
```bash
act -j flatpak -m gnome-version=49
```

**Run only linting:**
```bash
act -j lint
```

### Run a specific GNOME version:

```bash
# Build for GNOME 45
act -j flatpak --matrix gnome-version:45

# Build for GNOME 46
act -j flatpak --matrix gnome-version:46

# Build for GNOME 47
act -j flatpak --matrix gnome-version:47

# Build for GNOME 48
act -j flatpak --matrix gnome-version:48

# Build for GNOME 49
act -j flatpak --matrix gnome-version:49
```

## Using the Helper Script

We've provided a convenience script:

```bash
# Run all tests
./run-ci-locally.sh test

# Run Flatpak build for specific GNOME version
./run-ci-locally.sh flatpak 49

# Run Flatpak build for all GNOME versions
./run-ci-locally.sh flatpak-all

# Run linting
./run-ci-locally.sh lint

# Run everything
./run-ci-locally.sh all
```

## Troubleshooting

### Docker permission denied

If you get "permission denied" errors with Docker:

```bash
sudo usermod -aG docker $USER
```

Then log out and log back in.

### act can't find workflows

Make sure you're in the repository root directory:

```bash
cd /path/to/TFCBM
act -j test
```

### Container image pull errors

If you encounter errors pulling container images, try:

```bash
# Pull the image manually first
docker pull bilelmoussaoui/flatpak-github-actions:gnome-49

# Then run act
act -j flatpak --matrix gnome-version:49
```

### Resource constraints

The Flatpak builds can be resource-intensive. If you run into memory issues:

```bash
# Run one GNOME version at a time
./run-ci-locally.sh flatpak 49

# Or increase Docker's memory limit in Docker Desktop settings
```

## Advanced Options

### Dry run (don't actually execute)

```bash
act -j test -n
```

### Use specific Docker image

```bash
act -j test --platform ubuntu-latest=ubuntu:22.04
```

### Verbose output

```bash
act -j test -v
```

### Set environment variables

```bash
act -j test --env MY_VAR=value
```

## CI Workflow Overview

The workflow has three jobs:

1. **test** - Runs Python and Node.js tests
   - Sets up Python 3.11 and Node.js 20
   - Installs dependencies
   - Runs pytest for Python tests
   - Runs npm test for Node.js tests

2. **flatpak** - Builds Flatpak for GNOME 45-49
   - Matrix builds for each GNOME version
   - Creates version-specific manifests
   - Builds and bundles the Flatpak
   - Uploads artifacts

3. **lint** - Runs flatpak-builder-lint
   - Lints the manifest
   - Builds a repo and lints it
   - Checks for common issues

## Testing Before Push

**Recommended workflow:**

```bash
# 1. Run tests first (fast)
./run-ci-locally.sh test

# 2. If tests pass, build for latest GNOME version
./run-ci-locally.sh flatpak 49

# 3. If that succeeds, optionally test other versions
./run-ci-locally.sh flatpak 45
./run-ci-locally.sh flatpak 46

# 4. Run linting
./run-ci-locally.sh lint

# 5. If all passes, push to GitHub
git push
```

## Viewing Artifacts

After running locally, artifacts are created in:
- Test results: Check console output
- Flatpak bundles: `tfcbm-gnome{45,46,47,48,49}.flatpak`
- Lint results: Check console output

## Notes

- Local execution is slower than GitHub Actions runners
- Some features (like artifact uploads) may not work identically locally
- The workflow is configured to be permissive with test failures during development
- Flatpak builds require significant disk space (~2-3GB per GNOME version)

## Further Reading

- [act documentation](https://github.com/nektos/act)
- [GitHub Actions documentation](https://docs.github.com/en/actions)
- [Flatpak builder documentation](https://docs.flatpak.org/en/latest/flatpak-builder.html)
