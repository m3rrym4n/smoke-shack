<p align="center">
  <img src="assets/brand/smoke-shack-header-1280x640.png" alt="Smoke-Shack: a cook journal for pellet grills" width="800">
</p>

# Smoke-Shack

Smoke-Shack is a self-hosted cook journal for pellet grills. It records grill and probe data
from Home Assistant, turning each cook into a searchable history of temperatures, phases,
events, ingredients, notes, and results. It was built and tested with a Green Mountain Grills
Daniel Boone Prime WiFi through the `gmg-ha` integration. Smoke-Shack only reads from Home
Assistant and never controls the grill.

## Safety

Smoke-Shack is a journal and monitor, not a safety system. Always check your grill in person. Never leave a cooking grill unattended.

## Choose your setup

Choose the setup path that matches where you want to run Smoke-Shack and how your cooks are
recorded:

- **[Self-hosted with Docker (gmg-ha)](#setup-1-self-hosted-with-docker-gmg-ha)** — for Docker
  users whose grill data comes from the `gmg-ha` Home Assistant integration.
- **[Home Assistant App (gmg-ha)](#setup-2-home-assistant-app-gmg-ha)** — for Home Assistant
  OS or Supervised users who want Smoke-Shack to run inside Home Assistant.
- **[Self-hosted, manual mode](#setup-3-self-hosted-manual-mode-coming-soon)** — for users
  without Home Assistant or `gmg-ha`; coming soon.

## Status

Smoke-Shack is an early release. The author uses it daily with one grill, but expect rough
edges.

## Features

- Cook log with raw temperature history, cook details, photos, and CSV or JSON exports
- Live view of pit temperature, setpoint, food probes, targets, and grill status
- Automatic startup, cook, and cool-down phases, plus automatic and user-pinned events
- Custom meat groups and cohort statistics across comparable cooks
- Pantry for meat, pellets, and spice rubs
- Notes attached to a cook, pellets, or gear
- Ask the Pitmaster filters for cook-time averages, ranges, and time per pound
- Downloadable and shareable cook cards with photos, results, notes, phases, and charts

## How it works

The grill connects over Wi-Fi to the `gmg-ha` integration inside Home Assistant. Home
Assistant then provides the grill data to Smoke-Shack. Smoke-Shack does not talk to the grill:
it only reads from Home Assistant through its REST API and WebSocket connection, then records
each cook in its own SQLite database.

## Setup 1: Self-hosted with Docker (gmg-ha)

### Requirements

1. **Home Assistant**, running and reachable from the Smoke-Shack container, with a
   [long-lived access token](https://www.home-assistant.io/docs/authentication/#your-account-profile).
2. **The [`gmg-ha` integration](https://github.com/y3klab/gmg-ha)**, installed in Home
   Assistant through [HACS](https://www.hacs.xyz/). The grill must be in Wi-Fi mode and
   reachable on the local network because `gmg-ha` communicates with it over local UDP, with
   no cloud service. Smoke-Shack was built and tested with a Green Mountain Grills Daniel
   Boone Prime WiFi; other grills are untested.

   Credit goes to the `gmg-ha` project and its author for the Home Assistant integration.
3. **Docker with Docker Compose**.

Other Home Assistant grill integrations may work if you map their entities in
`entities.yaml`, but only `gmg-ha` is tested.

### Quick start with Docker Compose

Download this repository's [`compose.yml`](compose.yml), then create a `.env` file beside it
with the URL of your Home Assistant instance and a long-lived access token:

```dotenv
HA_URL=http://home-assistant-host:8123
HA_TOKEN=replace-with-a-long-lived-access-token
```

Start the app from the directory containing both files:

```sh
docker compose up -d
```

Open `http://docker-host:8011`. Keep the `.env` file out of version control; your container
platform's secret storage is also suitable for `HA_TOKEN`.

### Configure Home Assistant entities

`ENTITIES_CONFIG` tells Smoke-Shack where to find the YAML entity map. The included
[`config/entities.yaml`](config/entities.yaml) uses the entity IDs that `gmg-ha` creates in a
default installation:

```yaml
pit_climate: climate.green_mountain_grill
pit_temp: sensor.green_mountain_grill_temperature
probe1_temp: sensor.green_mountain_grill_probe_1_temperature
probe2_temp: sensor.green_mountain_grill_probe_2_temperature
probe1_connection: binary_sensor.green_mountain_grill_probe_1_connection
probe2_connection: binary_sensor.green_mountain_grill_probe_2_connection
probe1_climate: climate.green_mountain_grill_probe_1
probe2_climate: climate.green_mountain_grill_probe_2
fire_state: sensor.green_mountain_grill_fire_state
power_state: sensor.green_mountain_grill_power_state
warning: sensor.green_mountain_grill_warning
extra_probes: []
```

If your entity IDs differ, copy `config/entities.yaml` next to `compose.yml`, edit the copied
file, uncomment the entity-map volume line in `compose.yml`, and run `docker compose up -d` again.

Each value is a Home Assistant entity ID:

- `pit_climate`: the grill climate entity; supplies the operating mode and pit setpoint.
- `pit_temp`: the current pit temperature sensor.
- `probe1_temp` and `probe2_temp`: the current food-probe temperature sensors.
- `probe1_connection` and `probe2_connection`: binary sensors used to record when each probe
  connects or disconnects.
- `probe1_climate` and `probe2_climate`: probe climate entities; supply the target temperature
  for each probe.
- `fire_state`: the grill's fire-state sensor, such as startup, running, cool down, or off.
- `power_state`: the grill's power-state sensor.
- `warning`: the grill warning sensor; warning changes are added to the cook timeline.
- `extra_probes`: an optional YAML list of additional temperature sensor entity IDs. Leave it
  as `[]` when there are none.

All keys except `extra_probes` are required. Check your entity IDs in Home Assistant under
**Developer tools → States**. If they differ from the example, replace the values rather than
changing the keys.

## Setup 2: Home Assistant App (gmg-ha)

Requirements:

- Home Assistant OS or Supervised.
- The [`gmg-ha` integration](https://github.com/y3klab/gmg-ha), installed through
  [HACS](https://www.hacs.xyz/).
- Your grill in Wi-Fi mode on the same network as Home Assistant.

[![Add Repository](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Fm3rrym4n%2Fsmoke-shack)

Or add the repository manually:

```text
https://github.com/m3rrym4n/smoke-shack
```

The app uses the default `gmg-ha` entity names; details are in the app's Documentation tab.

## Setup 3: Self-hosted, manual mode (coming soon)

> **Coming soon.** Manual mode will let you log cooks by hand with no Home Assistant or grill integration. It is not available yet.

## Data and backups

`DATABASE_PATH` contains the SQLite database with cooks, samples, events, pantry records,
notes, profiles, and photo metadata. Uploaded photo files are stored under `PHOTO_DIR`. In the
Compose example both paths live in the `smoke-shack-data` volume, so preserve that volume
when replacing or upgrading the container.

Use the **Backup & Restore** link in the top navigation (or open `#backup` directly). **Download
backup** saves a zip containing the full database, all uploaded photos, and a manifest. Keep
preserving the data volume as an additional safeguard when replacing or upgrading the
container.

**Restore** uploads a Smoke-Shack backup zip and replaces all current data. Before replacing
anything, Smoke-Shack saves a safety copy named `pre-restore-<timestamp>.zip` next to the
database. Restore is refused while a cook is in progress. Backups from a newer database schema
are also refused; backups from older schemas are migrated forward after restore.

Home Assistant settings (`HA_URL` and `HA_TOKEN`) and `entities.yaml` are not included in the
archive, so preserve them separately.

## Screenshots

Screenshots coming soon.

## Development

Smoke-Shack uses Python 3.12. Create an environment and install the development dependencies
with the same tooling used by CI:

```sh
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -e '.[dev]'
```

Run the required checks:

```sh
.venv/bin/ruff check .
.venv/bin/mypy app
.venv/bin/pytest
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for the development and pull-request workflow.

## Support

For bugs and questions, open a [GitHub issue](https://github.com/m3rrym4n/smoke-shack/issues).
For security reports, use the **Report a vulnerability** button on the GitHub **Security** tab;
see [SECURITY.md](SECURITY.md) for details.

## License

Smoke-Shack is licensed under the [MIT License](LICENSE).
