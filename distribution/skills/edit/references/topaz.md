# Topaz API — opt-in finishing

## Authorization and credentials

Disabled by default. Only process media when the user explicitly requests Topaz for that media. A request to store a key, research the API, improve quality, make footage crisp, or run `/edit` is not permission to upload or start processing. Do not automatically enhance, denoise, sharpen, upscale, or interpolate. A future plan such as “after I grade, we will use Topaz” remains pending until that checkpoint is satisfied and execution is requested.

Honor the user's finishing order. If manual grading follows picture lock, finish the cut and hand it back for grading before Topaz. Never apply an automatic grade on their behalf.

Read the API key from `TOPAZ_API_KEY`, or the local private file `~/.config/topaz/api_key` (directory 0700, file 0600). Keep the secret outside this shared skill and all project manifests, commands, logs, exported artifacts, and screenshots. Load it in process memory and send it as the `X-API-Key` header only to the official API origin. Do not print the key or send it to signed upload/download hosts.

## Verified API flow

Documentation checked 2026-10-15; recheck schemas, model availability, limits, and pricing when executing:

- [Video quickstart](https://developer.topazlabs.com/getting-started/video-quickstart.md)
- [Proteus model](https://developer.topazlabs.com/video-models/proteus/proteus.md)
- [Documentation index](https://developer.topazlabs.com/llms.txt)

1. Inspect the exact source with ffprobe: dimensions, rational frame rate, frame count, duration, container, byte size, audio, color primaries/transfer/matrix and bit depth. Select output dimensions and a compatible codec/container. Preserve the approved cut, cadence, duration and audio unless explicitly requested otherwise.
2. For ordinary detail enhancement/upscaling, consult the current Proteus schema (`prob-4` at verification). The quickstart's Apollo `apo-8` example performs frame interpolation; do not copy it as an upscaling preset. Do not silently choose a generative model or invent texture/identity changes. Evaluate settings on a short representative sample within the authorized scope before a full export.
3. `POST https://api.topazlabs.com/video/` with `source`, `output`, and `filters` JSON per the current schema. Source metadata includes resolution, container, size, duration, frameRate and frameCount. Store the returned request ID and any available estimate without secrets. Request creation alone is not a completed render.
4. `PATCH /video/{requestID}/accept` to accept the job and obtain upload URLs. Follow the returned multipart instructions exactly. `PUT` the corresponding bytes to each signed URL and retain its ETag. Never attach the API credential to these storage requests.
5. `PATCH /video/{requestID}/complete-upload` with `{"uploadResults":[{"partNum":1,"eTag":"<returned ETag>"}]}` (include all actual parts). This queues processing. Treat acceptance/completion as potentially chargeable operations; proceed only within the user's explicit processing scope.
6. Poll `GET /video/{requestID}/status` with bounded backoff. Honor rate-limit responses. Persist the ID so an interrupted run can resume. Never blindly retry job creation or acceptance after an ambiguous network outcome; inspect known state first to avoid duplicate charges.
7. Download the completed result to the existing project's working area, retaining the original and graded master. Verify decoding, dimensions, frame count/duration, audio synchronization and color interpretation. Inspect skin, eyes, hair, edges, movement and transitions for halos, invented detail or temporal artifacts. Do not claim a successful upscale from a job ID alone.

Record source/output paths, model/settings, job ID, completion state and actual verification in the job ledger. Do not put signed URLs or credentials in durable shareable reports. Keep working renders separate from approved delivery files; preserve the existing edit backend and editable timeline.

This integration documents the API procedure. Credential validity and a live processing run are not established by saving this reference; report them separately when actually tested.
