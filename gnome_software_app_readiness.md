# GNOME Extension Fedora App Store Readiness

This document outlines the steps and considerations required to make the `tfcbm` GNOME Shell Extension available in the Fedora App Store, primarily through Flathub, which is the de-facto standard for distributing applications on Fedora and other Linux distributions.

## 1. Understanding the Distribution Channel: Flathub

Fedora's software center (GNOME Software) primarily uses Flatpak for third-party applications. Flathub is the central repository for Flatpak applications. To get the extension listed, it generally needs to be packaged as a Flatpak application (or a component within one).

It's important to clarify that GNOME Shell Extensions are often distributed directly through extensions.gnome.org, not typically as standalone Flatpak *applications*. However, if the goal is to have it appear in the "Fedora App Store" (GNOME Software), then it needs to either be:
1. Packaged as part of a larger application that is distributed via Flatpak.
2. If it's a standalone extension, the process for extensions.gnome.org is the more direct route.
3. Potentially, if it's considered a system component, it could be RPM packaged for Fedora's official repositories, but this is a higher bar for third-party software.

Assuming the goal is broad distribution and discoverability via GNOME Software, and considering "app store" implies Flatpak, we'll focus on the Flatpak/Flathub route, while also noting the extensions.gnome.org path.

## 2. Core Readiness Requirements

### 2.1. Project Metadata (`metadata.json`)

The `gnome-extension/metadata.json` file is crucial for extensions.gnome.org and provides essential information.
- **`uuid`**: Must be unique and match the directory name of the extension.
- **`name`**: User-friendly name.
- **`description`**: Clear and concise description of what the extension does.
- **`shell-version`**: Array of supported GNOME Shell versions. This needs to be actively maintained.
- **`url` (optional)**: Link to the project's homepage/repository.
- **`original-authors` (optional)**: Array of original authors.
- **`settings-schema` (optional)**: If the extension has configurable settings, this points to the GSettings schema file.

**Action:** Review `gnome-extension/metadata.json` for completeness and accuracy. Ensure `shell-version` is up-to-date with currently supported GNOME versions.

### 2.2. Licensing

The project needs a clear and open-source license. Flathub and Fedora's repositories generally require FOSS licenses.

**Action:** Ensure a `LICENSE` file is present in the root of the project (or explicitly within the `gnome-extension` directory) and that `metadata.json` refers to it if applicable.

### 2.3. Dependencies

The extension's dependencies need to be managed.
- **Node.js dependencies:** The `package.json` specifies Node.js dependencies. These are used during development/build but shouldn't be runtime dependencies for the GNOME Shell environment.
- **GNOME Shell/GJS dependencies:** Any GJS modules or system libraries used by `extension.js` or `src/` files need to be available in the target environment.

**Action:**
- Review `package.json` for build-time dependencies.
- Document any runtime GNOME/GJS dependencies required for the extension to function.

### 2.4. Build System

For Flatpak, a `flatpak-builder` manifest (`.yaml` or `.json`) would be needed. This manifest describes how to build the extension and its dependencies from source.

**Action:** Develop a `flatpak-builder` manifest. This would involve:
- Defining build dependencies (e.g., `nodejs`, `yarn` or `npm`).
- Specifying the build steps for the extension itself (e.g., `yarn install`, `yarn build` if applicable, then copying files to the correct GNOME Shell extension directory structure).

### 2.5. Internationalization (i18n)

For broad adoption, the extension should support multiple languages. This involves extracting translatable strings and providing translation files (`.po` files).

**Action:**
- Implement `gettext` for strings within `extension.js` and other relevant JS files.
- Set up a translation workflow (e.g., using `poedit` or integrating with a platform like Weblate).

### 2.6. User Interface and Experience (UI/UX)

The extension should adhere to GNOME Human Interface Guidelines (HIG) for a consistent user experience. This includes visual style, notification behavior, and settings dialogs.

**Action:** Review the extension's UI/UX against GNOME HIG.

### 2.7. Testing

Robust testing is essential. The `gnome-extension/tests/` directory indicates some testing is in place.

**Action:**
- Ensure unit and integration tests provide good coverage.
- Consider setting up automated testing within the Flatpak build environment.

### 2.8. Security Considerations

Extensions run with significant privileges within the user's session.
- **Input Validation:** Validate all inputs, especially from external sources or user configurations.
- **Privilege Separation:** If the extension interacts with external services (like `tfcbm_server.py`), ensure these interactions are secure and minimized.
- **Code Review:** Regular security reviews of the JavaScript code.

**Action:** Conduct a security review of the extension's code, especially how it interacts with the `tfcbm_server.py`.

## 3. Flathub-Specific Requirements

### 3.1. Application ID

Flatpak applications require a unique application ID (e.g., `org.example.AppName`). For a GNOME Extension, this might be `org.gnome.Shell.Extensions.TfCBM` or similar.

**Action:** Choose a suitable, reverse-DNS style application ID.

### 3.2. Manifest (`.yaml`)

As mentioned, a `flatpak-builder` manifest is required. This would be submitted to Flathub.

### 3.3. Build Process

Flathub will build the application from source using the provided manifest. The build must be reproducible.

## 4. Submission Process

### 4.1. Extensions.gnome.org

This is the most common and direct path for GNOME Shell Extensions.
- Create an account on extensions.gnome.org.
- Upload a `.zip` archive of the extension (containing `metadata.json`, `extension.js`, `schemas/`, `src/`, etc.).
- The extension will go through a review process by GNOME Shell Extension reviewers.

### 4.2. Flathub

If packaged as a Flatpak application (e.g., bundling the extension with a desktop application that manages it, or if the extension itself is considered an "app"):
- Follow the Flathub submission guidelines: [https://github.com/flathub/flathub/wiki/App-Submission](https://github.com/flathub/flathub/wiki/App-Submission)
- This typically involves submitting a pull request to the Flathub repository with the `flatpak-builder` manifest and relevant metadata.

## 5. Maintenance

### 5.1. GNOME Shell Version Compatibility

GNOME Shell Extensions frequently break with new GNOME Shell releases.
- **Action:** Regularly test against new GNOME Shell versions and update `metadata.json` and the extension code as needed.

### 5.2. Dependency Updates

Keep Node.js and other dependencies up-to-date to ensure security and compatibility.

## Summary of Key Actions:

1.  **Review `metadata.json`**: Ensure accuracy, completeness, and up-to-date `shell-version`.
2.  **Define a clear License**.
3.  **Document runtime dependencies**.
4.  **Implement Internationalization (i18n)**.
5.  **Review UI/UX** against GNOME HIG.
6.  **Enhance Test Coverage**.
7.  **Conduct Security Review**.
8.  **Choose an Application ID** (if going the Flatpak route).
9.  **Create a `flatpak-builder` manifest** (if going the Flatpak route).
10. **Prepare for submission to extensions.gnome.org** (primary route for extensions) **OR Flathub** (if packaged as an app).
11. **Plan for ongoing maintenance** (compatibility updates, security patches).
