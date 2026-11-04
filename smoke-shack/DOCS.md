# Smoke-Shack

## What Smoke-Shack is

Smoke-Shack is a cook journal and monitor. It reads grill and probe information from Home Assistant and records each cook.

Smoke-Shack is read-only toward Home Assistant. All grill controls, including start, shutdown, setpoint changes, and presets, are handled by `gmg-ha` and Home Assistant. Smoke-Shack never sends a command to the grill.

## Safety

Smoke-Shack is a journal and monitor, not a safety system. Always check your grill in person. Never leave a cooking grill unattended.

## Before you install

You need:

- Home Assistant.
- The [`gmg-ha` integration](https://github.com/y3klab/gmg-ha), installed through HACS.
- Your grill in Wi-Fi mode and connected to the same local network as Home Assistant.

Smoke-Shack has been tested only with a Green Mountain Grills Daniel Boone Prime WiFi. Other grills are untested. Smoke-Shack expects the default entity names created by `gmg-ha`.

## Install

1. **Click the button to add the repository** to your Home Assistant instance:

   [![Add Repository](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Fm3rrym4n%2Fsmoke-shack)

   Or add it manually in Settings → Apps → Install app → ⋮ → Repositories
   (Settings → Add-ons → Add-on store before Home Assistant 2026.2):

   ```text
   https://github.com/m3rrym4n/smoke-shack
   ```

2. **Find Smoke-Shack** in the app store and click **Install**.
3. **Click Start** when the install finishes.
4. **Open Smoke-Shack** from the Home Assistant sidebar.

## How a cook works

Use the **Order Pad** to plan a cook. You can choose meat and pellets, record rubs, sauces, prep time, and rotisserie use, then save the order. When Smoke-Shack detects the grill igniting, it starts a cook and uses the oldest planned order, if one exists.

Smoke-Shack detects ignition when Home Assistant reports the grill heating with the fire in startup or running state. The cook begins in **Startup**. It moves to **Cook** when the grill setpoint leaves its startup temperature of 150°F. It moves to **Cool down** when shutdown or the grill's cool-down state is detected. The cook closes when Home Assistant reports both the fire and grill power off. If cool-down does not finish within 90 minutes, Smoke-Shack closes the cook as incomplete.

During a cook, the live view shows the pit temperature and setpoint, connected probe temperatures and their targets, and the time spent in the startup, cook, and cool-down phases. It also charts temperatures and lists automatic changes and events you pin to the cook log.

After the cook, open it from the **Cook Log** to add or edit the result, notes, and photos. A finished cook can be exported as a PNG cook card with its cook details, phase times, chart, notes, result, and a selected photo.

## Your data

Cook data and photos are stored in the app's `/data` directory. Use **Backup & Restore** inside Smoke-Shack to download or restore a backup. Home Assistant backups also include the app's data.

Uninstalling the app deletes its data. Select **Keep backup** when uninstalling, or download a backup in Smoke-Shack first.

## Other ways to run Smoke-Shack

This page covers the Home Assistant App. To run Smoke-Shack on your own server with Docker, see the [README](https://github.com/m3rrym4n/smoke-shack#choose-your-setup). Manual mode (no Home Assistant) is coming soon.

## Troubleshooting

First, open **Developer tools → States** in Home Assistant. Check that the grill entities exist and match the default `gmg-ha` entity names expected by Smoke-Shack.

For connection or startup details, check the app's **Log** tab.
