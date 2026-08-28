# API Notes

Last checked: 2026-08-28.

## Immich

Source of truth: current generated Immich OpenAPI spec at
`immich-app/immich/open-api/immich-openapi-specs.json`, version `3.2.0-rc.0` when checked.

Live compatibility note: Immich `v2.7.5` was observed accepting the newer
`filter.personIds.any` request but ignoring that filter. For compatibility, this service verifies
that returned assets actually include the target person in `people[]`. If no verified assets are
returned, it retries the older top-level `personIds` search shape. This fallback remains API-only
and does not use Immich database internals.

Used endpoints:

- `GET /api/people`: stable. Supports `page`, `size`, `withHidden`. `PersonResponseDto`
  includes `isFavorite`, which this service uses for the default sync scope.
- `POST /api/search/metadata`: stable. Use `filter.personIds.any`, `filter.type.eq=IMAGE`,
  and `filter.visibility.eq=timeline`. Paginate with `assets.nextCursor`. On older Immich versions,
  fall back to top-level `personIds` only when the current filter shape yields no verified person
  matches.
- `GET /api/faces?id={assetId}`: stable. Returns asset faces with bounding boxes and nullable
  `person`.
- `GET /api/assets/{id}/original`: stable. Used only long enough to crop a training image.

Avoided endpoints:

- `GET /api/people/{id}/assets`: deprecated historically and absent from current OpenAPI.
- Immich PostgreSQL and filesystem internals.

## Frigate

Source of truth: current Frigate API docs under Integrations -> HTTP API -> Classification.

Used endpoints:

- `GET /api/faces`: returns `{face_name: [image_filename, ...]}`.
- `POST /api/faces/{name}/register`: multipart/form-data upload with required binary `file`.
  This endpoint creates/populates the identity as needed.

Avoided endpoints:

- `POST /api/faces/train/{name}/classify`: this classifies an existing Frigate train-directory
  image or event-derived face, not a direct upload path for Immich crops.
- `POST /api/faces/{name}/create`: on Frigate `0.17-0`, this was observed normalizing spaces to
  underscores while `register` stored uploaded images under the original name. To avoid empty
  duplicate identities, v1 uses `register` directly.
- Delete/rename endpoints. v1 is non-destructive and conservative on Immich renames.
- Frigate filesystem, SQLite, embeddings, and model files.
