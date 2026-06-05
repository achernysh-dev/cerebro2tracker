# Client setup: Cerebro2Tracker

## Required software

| Application | Purpose |
|---|---|
| **Cerebro** | Host application for the plugin |
| **Git for Windows** | Clone and update the code from GitHub |

No separate Python install, virtual environment, or pip step is required. Tracker API dependencies are bundled in `vendor/site-packages/`.

## First-time setup

```bat
git clone https://github.com/achernysh-dev/cerebro2tracker.git C:\cerebro2tracker
```

Configure Cerebro to load the plugin from the cloned folder (same studio setup you already use). The repo root must be on Python's path so `import twin_plugin` works.

Restart Cerebro after cloning.

### Sync settings (first run)

`sync_settings.json` is not stored in git. On first use the plugin creates:

```
%APPDATA%\cerebro2tracker\sync_settings.json
```

Enter your Yandex Tracker credentials there or via the **Sync to Tracker** UI:

- `tracker_token`
- `tracker_cloud_org_id`

## Update the plugin

```bat
cd C:\cerebro2tracker
git pull
```

Restart Cerebro. Your settings in `%APPDATA%\cerebro2tracker\` are not overwritten by `git pull`.

## What stays local (not from GitHub)

| Path | Contents |
|---|---|
| `%APPDATA%\cerebro2tracker\sync_settings.json` | Tokens, task map |
| `C:\cerebro2tracker\.env` | Optional dev secrets (if present) |
| `C:\cerebro2tracker\.venv\` | Optional dev venv (not required for clients) |

## Maintainer: refresh vendored dependencies

When upgrading the Tracker client library, run from the repo root:

```bat
scripts\vendor_deps.bat
```

Then commit the updated `vendor/site-packages/` folder.
