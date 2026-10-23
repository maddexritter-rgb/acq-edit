#!/usr/bin/env node
// Opt-in live native/agent qualification. Never part of the mock test suite.
import assert from 'node:assert/strict';
import path from 'node:path';
import { mkdir, readFile } from 'node:fs/promises';
import { randomUUID, createHash } from 'node:crypto';
import { spawnSync } from 'node:child_process';
import { DatabaseSync } from 'node:sqlite';

const [mode, directory, configFile] = process.argv.slice(2);
assert(['prepare', 'check'].includes(mode) && directory,
  'Usage: node scripts/native_agent_fixture.mjs prepare NEW_DIRECTORY CONFIG_JSON | check DIRECTORY');
const base = path.resolve(directory);
const json = async file => JSON.parse(await readFile(file, 'utf8'));
const digest = bytes => createHash('sha256').update(bytes).digest('hex');
function run(command, args) {
  const result = spawnSync(command, args, { maxBuffer: 128 * 1024 * 1024, timeout: 120000 });
  assert(!result.error && result.status === 0,
    `${command} failed: ${result.error?.message || result.stderr?.toString().slice(-2000)}`);
  return result.stdout;
}

if (mode === 'prepare') {
  assert(configFile, 'An existing toolkit config JSON is required; credentials are not copied');
  const existing = await json(path.resolve(configFile));
  assert(['filmcraft', 'resolve'].includes(existing.backend),
    'This fixture supports FilmCraft or Resolve; it never switches an existing project backend');
  assert(['codex', 'claude'].includes(existing.agent), 'Unknown configured agent');
  if (existing.backend === 'filmcraft') run(existing.filmcraft, ['--help']);
  else { assert(existing.resolvePython, 'Configured ResolvePython required'); run(existing.resolvePython, ['-c', 'print("ResolvePython available")']); }
  run('ffmpeg', ['-version']);
  // Exclusive creation prevents overwriting or replaying an earlier acceptance run.
  await mkdir(base, { mode: 0o700 });
  process.env.ACQ_EDIT_HOME = path.join(base, 'home');
  const { Store } = await import('../dist/store.js');
  const { createProject, importLocal, exportState } = await import('../dist/projects.js');
  const { saveConfig } = await import('../dist/config.js');
  const { atomicJson, sha256 } = await import('../dist/files.js');
  const config = {
    storageRoot: path.join(base, 'projects'), backend: existing.backend, agent: existing.agent,
    python: existing.python,
    ...(existing.backend === 'filmcraft' ? {filmcraft: existing.filmcraft} : {resolvePython: existing.resolvePython}),
    ...(existing.agentCommand ? { agentCommand: existing.agentCommand } : {}),
    agentTimeoutMs: existing.agentTimeoutMs || 600000, port: existing.port || 4317,
  };
  await saveConfig(config);
  const store = new Store(path.join(process.env.ACQ_EDIT_HOME, 'state.sqlite'));
  try {
    const project = await createProject(store, config.storageRoot, 'Synthetic native agent loop', config.backend, config.agent);
    const seed = path.join(base, 'synthetic.mp4');
    run('ffmpeg', ['-v', 'error', '-n', '-f', 'lavfi', '-i', 'testsrc2=size=640x360:rate=25:duration=4',
      '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=48000:duration=4', '-c:v', 'libx264',
      '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-shortest', seed]);
    const source = await importLocal(store, project.id, seed);
    const clip = { id: randomUUID(), projectId: project.id, number: 1, title: 'Synthetic native job test', currentVersionId: null };
    store.addClip(clip);
    const work = path.join(project.root, '10_WORK');
    const brain = path.join(work, 'brain-fixture.json'), selection = path.join(work, 'selection-fixture.json');
    await atomicJson(brain, { testFixture: true, purpose: 'Mechanical test; no live editorial guidance claimed' });
    await atomicJson(selection, { testFixture: true, purpose: 'Frozen synthetic geometry; not speech or human approval' });
    const plan = {
      schema: 'acq-edit/plan-v1', projectId: project.id, backend: project.backend, clipId: clip.id, title: clip.title,
      fps: { numerator: 25, denominator: 1 }, width: 640, height: 360, sampleRate: 48000,
      brain: { receiptPath: brain, sha256: await sha256(brain) },
      editorial: { selectionPath: selection, sha256: await sha256(selection), reviewed: true }, sources: [source],
      cuts: [0, 1].map(i => ({ id: `cut-${i}`, sourceId: source.id, sourceInFrame: i * 50,
        frames: 25, recordFrame: i * 25, audioInSample: i * 96000, audioSamples: 48000,
        wordIds: ['fixture'], boundaryEvidence: 'synthetic-fixture-not-speech' })),
      captions: [{ startFrame: 0, endFrame: 50, text: 'NATIVE AGENT LOOP',
        style: { size: 30, font: 'Arial', position: [320, 285] } }], graphics: [], framing: {}, audio: {},
    };
    const planPath = path.join(work, 'fixture-plan.json');
    await atomicJson(planPath, plan);
    const request = `Mechanical integration fixture: build exactly one existing clip ${clip.id} from the frozen synthetic plan ${planPath}.
This is not editorial design, speech content, or human approval. Do not fetch brain guidance, transcribe, choose words, change the plan, or call other agents.
ACQ_EDIT_TEST_FIXTURE=1 must be supplied by the operator. Read the native ${config.backend} adapter and packet documentation.
Use the toolkit native build/render commands, new packets and operation folders under this job directory. Do not substitute a shell-made final or copy an old render.
Capture the native fingerprint, inspect the exported geometry, publish the native receipt through the toolkit, and write result.json with the returned version ID.
Expected output: 50 frames, 640x360, 25 fps, NATIVE AGENT LOOP text. No optional audits, real projects, credentials, global skills or editor installation changes.`;
    const job = store.enqueueBuild(project.id, request);
    await exportState(store, project.id);
    const fixture = { project, clip, jobId: job.id, home: process.env.ACQ_EDIT_HOME, config, planPath };
    await atomicJson(path.join(base, 'fixture.json'), fixture);
    console.log(JSON.stringify({ fixture: path.join(base, 'fixture.json'), projectId: project.id,
      home: fixture.home, queuedJob: job.id,
      ...(config.backend === 'resolve' ? {requiredNativeProject: `ACQ_${project.id}`, hostPreparation: 'Create/open this exact empty Resolve project before dispatch. Do not close unrelated work. A blank Untitled Project is not this project.'} : {}),
      next: 'After host preparation, run worker with this ACQ_EDIT_HOME and ACQ_EDIT_TEST_FIXTURE=1; see docs/LIVE_AGENT_LOOP.md' }, null, 2));
  } finally { store.close(); }
} else {
  const f = await json(path.join(base, 'fixture.json'));
  const db = new DatabaseSync(path.join(f.home, 'state.sqlite'), { readOnly: true });
  const rows = (sql, ...args) => db.prepare(sql).all(...args).map(r => JSON.parse(r.data));
  try {
    const jobs = rows('SELECT data FROM jobs WHERE project_id=? ORDER BY rowid', f.project.id);
    assert.equal(jobs.length, 2, 'Expected one build and one revision; do not silently ignore duplicate jobs');
    assert(jobs.every(j => j.state === 'ready' && j.agentSession && !j.error), 'Both real agent jobs must finish ready');
    const versions = rows('SELECT data FROM versions WHERE clip_id=? ORDER BY rowid', f.clip.id);
    assert.equal(versions.length, 2, 'Expected two published versions');
    const [v1, v2] = versions;
    assert.equal(v2.parentId, v1.id); assert.equal(v1.jobId, jobs[0].id); assert.equal(v2.jobId, jobs[1].id);
    assert.equal(jobs[1].snapshot[0].version.id, v1.id);
    const feedback = rows('SELECT data FROM feedback WHERE version_id=?', v2.id)[0];
    assert.equal(feedback.decision, null, 'Changed version must require fresh review');
    const inspections = [], plans = [], pcm = [], audioData = [], pictures = [];
    for (const v of versions) {
      assert.equal(digest(await readFile(v.media)), v.sha256, 'Published media changed');
      assert.equal(digest(await readFile(v.nativeCheckpoint)), v.nativeFingerprint, 'Native checkpoint changed');
      const receipt = await json(v.receiptPath);
      assert.equal(receipt.backend, f.project.backend); assert.equal(receipt.jobId, v.jobId);
      assert.equal(receipt.nativeRendered, true);
      assert.deepEqual(receipt.expected, { frames: 50, width: 640, height: 360, fps: '25/1' });
      const result = await json(path.join(f.project.root, '10_WORK', 'jobs', v.jobId, 'result.json'));
      assert.deepEqual(result.versionIds, [v.id]); assert.equal(result.jobId, v.jobId);
      const probe = JSON.parse(run('ffprobe', ['-v', 'error', '-count_frames', '-show_streams', '-of', 'json', v.media]));
      const video = probe.streams.filter(s => s.codec_type === 'video');
      assert.equal(video.length, 1); assert.equal(video[0].nb_read_frames, '50');
      assert.equal(video[0].width, 640); assert.equal(video[0].height, 360); assert.equal(video[0].r_frame_rate, '25/1');
      assert.equal(probe.streams.filter(s => s.codec_type === 'audio').length, 1);
      const decodedAudio = run('ffmpeg', ['-v', 'error', '-i', v.media, '-map', '0:a:0', '-f', 'f32le', '-']);
      audioData.push(decodedAudio); pcm.push(digest(decodedAudio));
      pictures.push(digest(run('ffmpeg', ['-v', 'error', '-i', v.media, '-map', '0:v:0', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'])));
      inspections.push(await json(path.join(path.dirname(v.receiptPath), 'inspection.json')));
      plans.push(await json(v.planPath));
    }
    const failures = [];
    if (pcm[0] !== pcm[1]) failures.push('Caption-only revision changed decoded audio; exact-audio qualification failed');
    assert.equal(audioData[0].length, audioData[1].length, 'Decoded audio length changed');
    let signalEnergy = 0, differenceEnergy = 0, maxDifference = 0;
    for (let i = 0; i < audioData[0].length; i += 4) {
      const a = audioData[0].readFloatLE(i), b = audioData[1].readFloatLE(i), difference = b - a;
      assert(Number.isFinite(a) && Number.isFinite(b), 'Nonfinite audio sample');
      signalEnergy += a * a; differenceEnergy += difference * difference;
      maxDifference = Math.max(maxDifference, Math.abs(difference));
    }
    assert.notEqual(pictures[0], pictures[1], 'Caption revision produced identical pictures');
    assert.equal(plans[0].captions[0].text, 'NATIVE AGENT LOOP');
    assert.equal(plans[1].captions[0].text, 'REVISED AGENT LOOP');
    plans[1].captions[0].text = plans[0].captions[0].text;
    assert.deepEqual(plans[1], plans[0], 'Caption wording revision changed other plan fields');
    if (f.project.backend === 'filmcraft') {
      const native1 = JSON.stringify(inspections[0]), native2 = JSON.stringify(inspections[1]);
      assert(native1.includes('NATIVE AGENT LOOP') && native2.includes('REVISED AGENT LOOP'));
      assert.equal(native2.replaceAll('REVISED AGENT LOOP', 'NATIVE AGENT LOOP'), native1,
        'Native state changed beyond caption wording');
    } else {
      // Resolve duplicates native timelines for revisions. IDs/names and Fusion
      // graph hashes legitimately change; do not misreport full graph equivalence.
      const normalize = input => {
        const state = structuredClone(input), locations = new Map();
        for (const [kind, tracks] of Object.entries(state.tracks)) tracks.forEach((track,t) =>
          track.forEach((item,i) => locations.set(item.id, `${kind}/${t}/${i}`)));
        delete state.timeline; delete state.name;
        for (const tracks of Object.values(state.tracks)) for (const track of tracks) for (const item of track) {
          delete item.id;
          item.fusionCount = item.fusion.length; delete item.fusion;
          item.linkedIds = item.linkedIds.map(id => { assert(locations.has(id), 'Unknown native link'); return locations.get(id); }).sort();
        }
        return state;
      };
      assert.deepEqual(normalize(inspections[1]), normalize(inspections[0]), 'Resolve revision changed cuts, sources, properties, links or track state');
    }
    for (const source of rows('SELECT data FROM sources WHERE project_id=?', f.project.id)) {
      assert.equal(digest(await readFile(source.path)), source.sha256, 'Project-owned source changed');
    }
    const pending = rows('SELECT data FROM deferred_feedback WHERE clip_id=? AND consumed_by IS NULL', f.clip.id);
    assert.equal(pending.length, 1, 'Add the documented late comment while the real revision is running');
    assert.equal(pending[0].sourceVersion.id, v1.id);
    assert.equal(pending[0].submitted.comments.length, 1);
    assert.equal(pending[0].latest.comments.length, 2);
    assert.equal(jobs[1].snapshot[0].feedback.comments.length, 1, 'Late feedback leaked into submitted snapshot');
    console.log(JSON.stringify({ passed: failures.length === 0, failures, scope: `synthetic ${f.project.backend} agent/review integration, not editorial approval`,
      agent: f.project.agent, nativeJobs: jobs.length, versions: versions.map(v => v.id),
      sourceAndPublishedHashesPreserved: true, nativeChange: f.project.backend === 'filmcraft' ? 'caption text only' : 'caption plan changed; native cuts/sources/properties/links preserved; Fusion appearance requires inspection',
      decodedAudioIdentical: pcm[0] === pcm[1],
      audioDifference: {maxSampleDifference: maxDifference, rmsRelativeDb: differenceEnergy && signalEnergy ? 10 * Math.log10(differenceEnergy / signalEnergy) : null},
      renderedPicturesChanged: true, lateCommentPreserved: true }, null, 2));
    if (failures.length) process.exitCode = 1;
  } finally { db.close(); }
}
