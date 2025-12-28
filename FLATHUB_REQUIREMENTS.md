# Flathub Submission Requirements

## Important Notice

**AI-generated submissions are not allowed** as these are typically low-quality, often violate the submission requirements, and create unnecessary work for the reviewers. They also raise ethical and legal concerns such as potential license infringement and resource wastage.

Flathub reserves the right to reject such submissions without any review.

## Prerequisites

### 1. Install org.flatpak.Builder

```bash
flatpak install -y flathub org.flatpak.Builder
```

### 2. Add Flathub Repository User-wide

```bash
flatpak remote-add --if-not-exists --user flathub https://dl.flathub.org/repo/flathub.flatpakrepo
```

## Build and Test Process

### Build Your Manifest

Flathub recommends using org.flatpak.Builder to build the application.

```bash
flatpak run --command=flathub-build org.flatpak.Builder --install <manifest>
```

Example for this project:
```bash
flatpak run --command=flathub-build org.flatpak.Builder --install org.tfcbm.ClipboardManager.yml
```

### For Extra Data

If you are using extra-data:

```bash
flatpak run --command=flathub-build org.flatpak.Builder <manifest>
flatpak install --user -y ./repo $FLATPAK_ID
```

### Run and Test

```bash
flatpak run <app-id>
```

Example for this project:
```bash
flatpak run org.tfcbm.ClipboardManager
```

## Linter Validation

### Run Linter on Manifest

```bash
flatpak run --command=flatpak-builder-lint org.flatpak.Builder manifest <manifest>
```

Example for this project:
```bash
flatpak run --command=flatpak-builder-lint org.flatpak.Builder manifest org.tfcbm.ClipboardManager.yml
```

### Run Linter on Repository

```bash
flatpak run --command=flatpak-builder-lint org.flatpak.Builder repo repo
```

## Current Linter Results

### Manifest Linter Errors

The following errors were found when running the linter on the manifest:

1. **finish-args-portal-talk-name**: finish-args has talk-name access to XDG Portal busnames
2. **finish-args-flatpak-spawn-access**: finish-args has access to flatpak-spawn
3. **appid-url-not-reachable**: Tried https://tfcbm.org
4. **finish-args-freedesktop-dbus-system-talk-name**: finish-args has system talk-name access to org.freedesktop.DBus or its sub-bus name
5. **finish-args-arbitrary-dbus-access**: finish-args has socket access to full system or session bus

### Repository Linter Errors

The following errors were found when running the linter on the repository:

1. **finish-args-arbitrary-dbus-access**: finish-args has socket access to full system or session bus
2. **finish-args-freedesktop-dbus-system-talk-name**: finish-args has system talk-name access to org.freedesktop.DBus or its sub-bus name
3. **finish-args-flatpak-spawn-access**: finish-args has access to flatpak-spawn
4. **appstream-missing-screenshots**: Catalogue file has no screenshots. Please check if screenshot URLs are reachable
5. **finish-args-portal-talk-name**: finish-args has talk-name access to XDG Portal busnames
6. **appstream-failed-validation**: Metainfo file org.tfcbm.ClipboardManager.metainfo.xml has failed validation
   - Error: `E:org.tfcbm.ClipboardManager.metainfo.xml:url-invalid-type:69 Invalid 'type' property for this 'url' tag`
7. **appid-url-not-reachable**: Tried https://tfcbm.org

## Action Items to Fix Linter Errors

### 1. Fix AppStream Metadata

- [ ] Fix the invalid URL type in `org.tfcbm.ClipboardManager.metainfo.xml` at line 69
- [ ] Add screenshots to the AppStream metadata or ensure screenshot URLs are reachable

### 2. Address Permission Warnings

Some of the permission errors may require exceptions from Flathub. Review each permission:

- [ ] **DBus Access**: Review if full system/session bus access is necessary. Consider using specific talk-name permissions instead
- [ ] **Flatpak Spawn**: Document why flatpak-spawn access is needed (likely for GNOME extension installation)
- [ ] **Portal Access**: Document why XDG Portal busname access is needed
- [ ] **System DBus**: Document why system bus access to org.freedesktop.DBus is needed

### 3. Fix or Document Homepage URL

- [ ] Either make https://tfcbm.org reachable or update the homepage URL in the manifest and metainfo file

### 4. Request Exceptions if Needed

For certain errors you might need an exception. Consult the [Flathub linter documentation](https://docs.flathub.org/linter) for details on how to request exceptions.

## Submission

Once all the above steps are complete and linter issues are resolved (or exceptions obtained), you can open a submission pull request to Flathub.

## Resources

- [Flathub Submission Documentation](https://docs.flathub.org/)
- [Flathub Linter Documentation](https://docs.flathub.org/linter)
- [AppStream Specification](https://www.freedesktop.org/software/appstream/docs/)
