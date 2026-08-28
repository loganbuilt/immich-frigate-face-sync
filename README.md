# immich-frigate-face-sync

`immich-frigate-face-sync` enrolls selected known people from Immich into Frigate's native face
recognition library. Immich remains the identity and source-photo system. Frigate owns real-time
recognition and embeddings.

```text
Immich API -> local crop/selection -> Frigate API
```

The default UI is Immich itself: name a person, mark them as favorite, and this bridge adds a small
set of representative face crops to Frigate.

## Requirements

- Immich with API access and facial recognition/person assignments enabled.
- Frigate with face recognition enabled.
- Docker Compose.

API assumptions are recorded in [docs/api-notes.md](docs/api-notes.md).

## Frigate Setup

Frigate must have object detection and face recognition enabled before this bridge can enroll
training images.

Minimal global configuration:

```yaml
objects:
  track:
    - person
    - car

face_recognition:
  enabled: true
  model_size: small
  min_area: 750
```

`person` is required because Frigate only runs face recognition after a person is detected. For the
default COCO model, use `car` for normal vehicle detection. Do not add `face` to `objects.track`
unless you are using a Frigate+ or custom model that natively detects `face`.

After changing Frigate config, restart Frigate and confirm:

```bash
curl http://frigate:5000/api/config
curl http://frigate:5000/api/faces
```

In the Frigate UI, imported images should appear under **Settings -> Face Library** after the bridge
successfully registers them. Recent recognitions and event sub-labels require new camera events after
face recognition is enabled.

## Quick Start

```bash
git clone https://github.com/<owner>/immich-frigate-face-sync.git
cd immich-frigate-face-sync
cp .env.example .env
nano .env
docker compose up -d
```

Start with `DRY_RUN=true`. Once the logs show the intended enrollments, set `DRY_RUN=false` and
restart the container.

## API Keys And Secrets

### Immich API Key

Create the key from your Immich user/account settings. On current Immich versions with scoped API
keys, select the narrow read permissions this bridge needs:

- `person.read`: list people and read favorite/hidden/name metadata.
- `asset.read`: search assets that contain a selected person.
- `asset.download`: download the original image long enough to crop a face.
- `face.read`: read Immich face bounding boxes and person assignments.

Optional but useful:

- `server.about`: version/about checks if future releases add explicit startup validation.

Do not grant Immich write permissions for this service. It does not need `person.update`,
`face.update`, `asset.upload`, `asset.delete`, `apiKey.*`, or admin permissions.

Older Immich releases may not support fine-grained API-key permissions. If your UI only offers an
all-or-nothing key, the bridge will work, but treat that key as highly privileged and store it as a
secret.

### Frigate Authentication

For a normal Docker deployment, `FRIGATE_API_KEY` is usually not needed. Frigate documents two API
surfaces:

- Port `5000`: internal unauthenticated UI/API. Frigate intends this for trusted Docker-network
  integrations. Recommended when this bridge runs beside Frigate on the same private Docker network.
- Port `8971`: authenticated UI/API. Use this when calling through Frigate's authenticated port or a
  reverse proxy.

If you use port `5000`, configure:

```env
FRIGATE_URL=http://frigate:5000
# Leave FRIGATE_API_KEY unset
```

If you use authenticated Frigate access, log in to Frigate and supply a bearer JWT token:

```bash
curl -i -X POST https://frigate.example.com/api/login \
  -H "Content-Type: application/json" \
  -d '{"user":"admin","password":"your_password"}'
```

Take the returned JWT token from the session cookie and configure:

```env
FRIGATE_URL=https://frigate.example.com
FRIGATE_API_KEY=that-jwt-token
```

Frigate bearer tokens follow Frigate's configured session lifetime and can expire. For an appliance
deployment, the cleaner setup is usually private Docker-network access to port `5000`, with network
access limited to trusted containers only.

### Where To Put Secrets

The simplest setup is `.env`:

```env
IMMICH_API_KEY=...
FRIGATE_API_KEY=...
```

Keep `.env` private. It is ignored by git in this repository.

For Docker secrets or mounted files, prefer the file variables:

```env
IMMICH_API_KEY_FILE=/run/secrets/immich_api_key
FRIGATE_API_KEY_FILE=/run/secrets/frigate_api_key
```

Do not set both `IMMICH_API_KEY` and `IMMICH_API_KEY_FILE`, or both `FRIGATE_API_KEY` and
`FRIGATE_API_KEY_FILE`; startup validation rejects ambiguous secret configuration.

## Configuration

| Variable | Default | Description |
| --- | --- | --- |
| `IMMICH_URL` | required | Immich base URL, with or without `/api`. |
| `IMMICH_API_KEY` | required | Immich API key. |
| `IMMICH_API_KEY_FILE` | unset | File containing the Immich API key, for Docker secrets. |
| `FRIGATE_URL` | required | Frigate base URL, with or without `/api`. |
| `FRIGATE_API_KEY` | unset | Optional bearer token for deployments that require it. |
| `FRIGATE_API_KEY_FILE` | unset | File containing the Frigate API key. |
| `SYNC_INTERVAL` | `24h` | Duration using `s`, `m`, `h`, or `d`. |
| `FACES_PER_PERSON` | `10` | Target managed Immich-derived samples per person. |
| `PEOPLE_MODE` | `favorites` | `favorites` or `all`. |
| `DRY_RUN` | `false` | Discover and rank candidates without writing to Frigate. |
| `RUN_ONCE` | `false` | Sync once, then exit. |
| `DATA_DIR` | `/data` | SQLite state directory. |
| `LOG_LEVEL` | `INFO` | Python logging level. |
| `HEALTH_PORT` | `8080` | Local health endpoint port. |

## Synchronization

The service is additive and non-destructive.

- Eligible people are named, visible, and favorited in Immich by default.
- It searches Immich assets for each person, retrieves face bounding boxes, downloads originals only
  long enough to crop a face image, and uploads the crop to Frigate.
- SQLite records Immich person IDs, Frigate names, Immich face IDs, and content hashes.
- Restarts do not upload already synchronized faces again.
- Unfavoriting a person stops future management but does not delete Frigate identities or images.
- Immich renames are logged; existing Frigate names are retained unless a future supported rename
  workflow is added.

## Privacy

This service runs locally. It has no telemetry, no analytics, no cloud dependency, and no persistent
photo cache. Original Immich assets are held in memory only long enough to crop JPEG training images.
Frigate generates and owns its own embeddings.

## Troubleshooting

- `Invalid configuration`: check required variables and avoid setting both `*_KEY` and `*_KEY_FILE`.
- No favorite people found: verify people are named, visible, and marked favorite in Immich.
- No suitable faces: Immich must have facial recognition complete and source assets available.
- Frigate rejects uploads: confirm `face_recognition.enabled: true` and that the upload works in the
  Frigate Face Library UI.
- Docker networking: inside Compose, use service names such as `http://immich-server:2283` and
  `http://frigate:5000`, not host-only names.
- Reverse proxies: configure base URLs that point to the real API and do not append `/api/api`.

## Development

```bash
python3.13 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
ruff check .
mypy src
pytest
docker build -t immich-frigate-face-sync:test .
```

The release workflow builds and tests pull requests. On tags such as `v0.1.0`, it publishes a
multi-arch image to:

```text
ghcr.io/<owner>/immich-frigate-face-sync:v0.1.0
ghcr.io/<owner>/immich-frigate-face-sync:0.1.0
ghcr.io/<owner>/immich-frigate-face-sync:0.1
ghcr.io/<owner>/immich-frigate-face-sync:latest
```
