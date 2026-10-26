#!/usr/bin/env node
// Opt-in live native/agent qualification. Never part of the mock test suite.
import assert from 'node:assert/strict';
import path from 'node:path';
import { mkdir, readFile } from 'node:fs/promises';
import { randomUUID, createHash } from 'node:crypto';
import { spawnSync } from 'node:child_process';
import { DatabaseSync } from 'node:sqlite';

const [mode, directory, configFile, scenario = 'caption'] = process.argv.slice(2);
assert(['caption','tracking','panels','recut','music'].includes(scenario), 'Unknown live fixture scenario');
assert(['prepare', 'check'].includes(mode) && directory,
  'Usage: node scripts/native_agent_fixture.mjs prepare NEW_DIRECTORY CONFIG_JSON [caption|tracking|panels|recut|music] | check DIRECTORY');
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
    run('ffmpeg', ['-v', 'error', '-n', '-f', 'lavfi', '-i', scenario==='panels'?'color=red:size=640x360:rate=25:duration=4,drawbox=x=220:y=100:w=16:h=100:color=white:t=fill':`testsrc2=size=640x360:rate=25:duration=${4}`,
      '-f', 'lavfi', '-i', scenario==='recut'?'aevalsrc=if(lt(t\\,2)\\,0.12*sin(2*PI*440*t)\\,0.12*sin(2*PI*880*t)):s=48000:d=4':`sine=frequency=440:sample_rate=48000:duration=${4}`, '-c:v', 'libx264',
      '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-shortest', seed]);
    const rawSource = await importLocal(store, project.id, seed);
    const work = path.join(project.root, '10_WORK');
    let source=rawSource,sourcePreparation;
    if(config.backend==='resolve'){
      const helper=path.resolve('distribution/skills/assembly-design/scripts/prepare_audio_precision.py');
      const prepared=path.join(work,'precision-source');
      run(config.python,[helper,'--source',rawSource.path,'--output-dir',prepared,'--sample-rate','48000']);
      const receiptPath=path.join(prepared,'audio_precision_source.json'),receipt=await json(receiptPath);
      assert.equal(receipt.status,'PCM_PREPARED_PICTURE_CLOCK_VERIFIED');
      assert.equal(receipt.source_sha256,rawSource.sha256);assert.equal(receipt.video_packets_and_pts_identical,true);
      source=await importLocal(store,project.id,receipt.media_path);assert.equal(source.sha256,receipt.media_sha256);
      sourcePreparation={owner:'assembly-design',rawSourceId:rawSource.id,preparedSourceId:source.id,receiptPath,receiptSha256:await sha256(receiptPath),helperSha256:await sha256(helper)};
    }
    const clip = { id: randomUUID(), projectId: project.id, number: 1, title: 'Synthetic native job test', currentVersionId: null };
    store.addClip(clip);
    const brain = path.join(work, 'brain-fixture.json'), selection = path.join(work, 'selection-fixture.json');
    await atomicJson(brain, { testFixture: true, purpose: 'Mechanical test; no live editorial guidance claimed' });
    await atomicJson(selection, { testFixture: true, purpose: 'Frozen synthetic geometry; not speech or human approval' });
    let plan = {
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
    if (scenario === 'tracking') {
      plan.width=360;plan.height=640;
      plan.captions[0].style.position=[180,550];
      const decision=path.join(work,'framing-fixture.json');
      await atomicJson(decision,{owner:'horizontal-to-vertical',testFixture:true,purpose:'Frozen source-local tracking transport; no subject detection claimed'});
      plan.framing={schema:'acq-edit/framing-v1',receiptPath:decision,receiptSha256:await sha256(decision),shots:Object.fromEntries(plan.cuts.map((cut,index)=>{
        const xs=Array.from({length:cut.frames},(_,i)=>index===0?100.25+.5*i:350.25-.5*i);
        return [cut.id,{mode:'tracked-crop',sourceWidth:640,sourceHeight:360,x:xs[0],y:20,width:180,height:320,xByFrame:xs,sourceRange:{sourceId:source.id,sha256:source.sha256,inFrame:cut.sourceInFrame,frames:cut.frames}}];
      }))};
    }
    if(scenario==='panels'){
      const seedB=path.join(base,'camera-b.mp4');
      run('ffmpeg',['-v','error','-n','-f','lavfi','-i','color=blue:size=640x360:rate=25:duration=4,drawbox=x=280:y=100:w=16:h=100:color=white:t=fill','-c:v','libx264','-pix_fmt','yuv420p',seedB]);
      const second=await importLocal(store,project.id,seedB),seedPlan=path.join(work,'panel-seed-plan.json'),secondPath=path.join(work,'panel-camera-source.json');
      await atomicJson(seedPlan,plan);await atomicJson(secondPath,second);
      plan=JSON.parse(run(config.python,[path.resolve('scripts/panel_agent_fixture.py'),'prepare',seedPlan,secondPath]));
    }
    if(scenario==='recut'){
      const musicSeed=path.join(base,'music.wav');
      run('ffmpeg',['-v','error','-n','-f','lavfi','-i','sine=frequency=220:sample_rate=48000:duration=4','-c:a','pcm_s16le',musicSeed]);
      const music=await importLocal(store,project.id,musicSeed),seedPlan=path.join(work,'recut-seed-plan.json'),musicPath=path.join(work,'music-source.json');
      await atomicJson(seedPlan,plan);await atomicJson(musicPath,music);
      plan=JSON.parse(run(config.python,[path.resolve('scripts/recut_agent_fixture.py'),'prepare',seedPlan,musicPath]));
      await atomicJson(path.join(base,'revision-request.json'),{
        notes:'Remove the first passage cut-0 entirely. Keep only cut-1 with its original source picture and audio ranges, now at recordFrame 0. Make a new synthetic selection receipt explicitly recording that removal. Retain the surviving fixed crop only and create a fresh framing receipt. Change the caption to RETAINED SECOND PASSAGE, startFrame 0, endFrame 25, same style. Retain the existing music asset and gain, but set sourceInSample 48000, samples 48000, startFrame 0 with a fresh music decision receipt. Move the existing 25-frame graphic from startFrame 25 to 0 without changing its asset. Address every finishing owner in a pinned recut-finishing receipt. Use spoken-recut, preserve the published parent and working native state, render natively, pass recutVerification, and publish a new 25-frame version. This is the same explicit synthetic fixture with ACQ_EDIT_TEST_FIXTURE=1; do not fetch brain guidance, transcribe, invent speech evidence or change any other fields.',
        comment:'Remove the opening passage; retain the second passage and retime its dependent layers.',
        lateComment:'Added while the recut is running: keep this note for the next submission, bound to the original version.'
      });
    }
    if(scenario==='music'){
      const sources=[];
      for(const hz of [220,1320]){const seed=path.join(base,`music-${hz}.wav`);run('ffmpeg',['-v','error','-n','-f','lavfi','-i',`sine=frequency=${hz}:sample_rate=48000:duration=4`,'-c:a','pcm_s16le',seed]);sources.push(await importLocal(store,project.id,seed))}
      plan.sources.push(sources[0]);await atomicJson(path.join(base,'replacement-source.json'),sources[1]);
      const receipt=path.join(work,'music-selection-fixture.json');await atomicJson(receipt,{testFixture:true,owner:'music',toneHz:220,notAuditionEvidence:true});
      plan.audio={gainDb:-3,music:[5,30].map((frame,index)=>({id:`bed-${index}`,sourceId:sources[0].id,startFrame:frame,sourceInSample:48000,samples:28800,gainDb:-12,fadeInSamples:3840,fadeOutSamples:3840,receiptPath:receipt,receiptSha256:null}))};
      for(const bed of plan.audio.music)bed.receiptSha256=await sha256(receipt);
      await atomicJson(path.join(base,'revision-request.json'),{
        notes:`Replace only music placement bed-0 (musicIndices [0]) with the already registered 1320 Hz PCM source described in ${path.join(base,'replacement-source.json')}. Append that exact source record to a new plan and create a new synthetic music decision receipt with notAuditionEvidence true. Change only bed-0 sourceId, receiptPath and receiptSha256. Keep its source offset, timing, duration, gain and fades unchanged. Preserve bed-1, dialogue, cuts, captions, framing and graphics. Use the native music-replacement operation with the pinned published previous plan and a fresh native inspection; render in ${config.backend} and publish a new immutable version. This is the same synthetic mechanical fixture with ACQ_EDIT_TEST_FIXTURE=1; no audition, new editorial design, transcription or brain fetch is requested.`,
        comment:'Replace only the first music bed. Keep the second bed and all pictures unchanged.',
        lateComment:'Added while music replacement is running: leave this note for the next submission; do not change the current job.'
      });
    }
    const planPath = path.join(work, 'fixture-plan.json');
    await atomicJson(planPath, plan);
    const request = `Mechanical integration fixture: build exactly one existing clip ${clip.id} from the frozen synthetic plan ${planPath}.
This is not editorial design, speech content, or human approval. Do not fetch brain guidance, transcribe, choose words, change the plan, or call other agents.
ACQ_EDIT_TEST_FIXTURE=1 must be supplied by the operator. Read the native ${config.backend} adapter and packet documentation.
Use the toolkit native build/render commands, new packets and operation folders under this job directory. Do not substitute a shell-made final or copy an old render.
Capture the native fingerprint, inspect the exported geometry, publish the native receipt through the toolkit, and write result.json with the returned version ID.
Expected output: ${plan.cuts.reduce((n,c)=>n+c.frames,0)} frames, ${plan.width}x${plan.height}, 25 fps, NATIVE AGENT LOOP text. ${scenario === 'panels' ? 'Read NATIVE_PANELS.md and preserve all native independent camera panels, curves, source clocks and the fixed caption; no flattened replacement.' : ''} ${scenario === 'tracking' ? 'Preserve the complete frozen tracking curves and fixed caption; execute native framing, not a pre-rendered replacement.' : ''} No optional audits, real projects, credentials, global skills or editor installation changes.`;
    const job = store.enqueueBuild(project.id, request);
    await exportState(store, project.id);
    const fixture = { project, clip, jobId: job.id, home: process.env.ACQ_EDIT_HOME, config, planPath, scenario, initialPlanSha256: await sha256(planPath), archivePinsRequired: true,...(sourcePreparation?{sourcePreparation}:{}) };
    if(scenario==='tracking')await atomicJson(path.join(base,'revision-request.json'),{notes:'Revise only the existing horizontal tracking curve for cut-0: xByFrame[i] = 80.25 + i for all 25 frames, with x = 80.25. Leave cut-1 exactly as it is. Preserve all cuts, source ranges, Y, scale, captions, graphics and audio. Use the tracking-framing operation, pinned previous plan and a fresh framing decision receipt. This is the same synthetic fixture with ACQ_EDIT_TEST_FIXTURE=1; no new editorial design, transcription or brain fetch. Render natively and publish a new version.',comment:'At the opening, change only the specified X curve. Keep the caption wording and second shot unchanged.',lateComment:'Added while tracking revision is running: leave this note for the next submission; do not change the current job.'});
    if(scenario==='panels')await atomicJson(path.join(base,'revision-request.json'),{notes:'Revise only cut-0 existing panels: move top to y=320 and bottom to y=0, keeping each rectangle 360x320. Set the top camera crop x=80.25 and xByFrame[i]=80.25+0.75*i for all 25 frames. Set the bottom camera crop x=60. Preserve all other crop fields, cuts, source identities/ranges/sync, cut-1 and cut-2, captions, graphics and audio. Use panel-framing with pinned previous plan and targets cut-0 panelIds top/bottom, a fresh Assembly Design camera-layout receipt and a fresh horizontal-to-vertical framing receipt. This is the same synthetic fixture with ACQ_EDIT_TEST_FIXTURE=1; no new moment selection, transcription or brain fetch. Render natively and publish a new version.',comment:'At the opening, swap the two panels and apply only the specified crops and curve. Keep the later split unchanged.',lateComment:'Added while panel revision is running: leave this note for the next submission; do not change the current job.'});
    await atomicJson(path.join(base, 'fixture.json'), fixture);
    console.log(JSON.stringify({ fixture: path.join(base, 'fixture.json'), projectId: project.id,
      home: fixture.home, queuedJob: job.id,
      ...(config.backend === 'resolve' ? {requiredNativeProject: `ACQ_${project.id}`, hostPreparation: 'Select the empty startup workspace or this exact toolkit project before dispatch. The agent can pin doctor.native.emptyWorkspace in its build packet to create the project. Do not close unrelated work.'} : {}),
      next: 'After host preparation, run worker with this ACQ_EDIT_HOME and ACQ_EDIT_TEST_FIXTURE=1; see docs/LIVE_AGENT_LOOP.md' }, null, 2));
  } finally { store.close(); }
} else {
  const f = await json(path.join(base, 'fixture.json'));
  if(f.scenario==='music'){console.log(run(f.config.python,[path.resolve('scripts/music_agent_fixture.py'),path.join(base,'fixture.json')]).toString());process.exit(0)}
  if(f.scenario==='recut'){console.log(run(f.config.python,[path.resolve('scripts/recut_agent_fixture.py'),'check',path.join(base,'fixture.json')]).toString());process.exit(0)}
  const tracking=f.scenario==='tracking',panels=f.scenario==='panels',vertical=tracking||panels,expectedWidth=vertical?360:640,expectedHeight=vertical?640:360,expectedFrames=panels?75:50;
  if(f.initialPlanSha256)assert.equal(digest(await readFile(f.planPath)),f.initialPlanSha256,'Frozen fixture plan changed');
  const db = new DatabaseSync(path.join(f.home, 'state.sqlite'), { readOnly: true });
  const rows = (sql, ...args) => db.prepare(sql).all(...args).map(r => JSON.parse(r.data));
  try {
    if(f.sourcePreparation){
      const preparation=f.sourcePreparation,receipt=await json(preparation.receiptPath);
      assert.equal(digest(await readFile(preparation.receiptPath)),preparation.receiptSha256,'PCM preparation receipt changed');
      assert.equal(receipt.status,'PCM_PREPARED_PICTURE_CLOCK_VERIFIED');assert.equal(receipt.video_packets_and_pts_identical,true);
      const [raw]=rows('SELECT data FROM sources WHERE id=?',preparation.rawSourceId),[prepared]=rows('SELECT data FROM sources WHERE id=?',preparation.preparedSourceId);
      assert(raw&&prepared&&raw.projectId===f.project.id&&prepared.projectId===f.project.id,'Prepared source lineage differs');
      assert.equal(digest(await readFile(raw.path)),raw.sha256);assert.equal(raw.sha256,receipt.source_sha256);
      assert.equal(digest(await readFile(prepared.path)),prepared.sha256);assert.equal(prepared.sha256,receipt.media_sha256);
      assert((await json(f.planPath)).sources.some(s=>s.id===prepared.id&&s.sha256===prepared.sha256),'Fixture bypassed prepared PCM');
    }
    const jobs = rows('SELECT data FROM jobs WHERE project_id=? ORDER BY rowid', f.project.id);
    assert.equal(jobs.length, 2, 'Expected one build and one revision; do not silently ignore duplicate jobs');
    assert(jobs.every(j => j.state === 'ready' && j.agentSession && !j.error), 'Both real agent jobs must finish ready');
    const versions = rows('SELECT data FROM versions WHERE clip_id=? ORDER BY rowid', f.clip.id);
    assert.equal(versions.length, 2, 'Expected two published versions');
    const archivedArtifactsPinned = versions.every(v => v.planSha256 && v.receiptSha256 && v.inspectionPath && v.inspectionSha256);
    if (tracking || panels || f.archivePinsRequired) assert(archivedArtifactsPinned, 'This fixture requires pinned plan, receipt and inspection artifacts');
    const [v1, v2] = versions;
    assert.equal(v2.parentId, v1.id); assert.equal(v1.jobId, jobs[0].id); assert.equal(v2.jobId, jobs[1].id);
    assert.equal(jobs[1].snapshot[0].version.id, v1.id);
    const feedback = rows('SELECT data FROM feedback WHERE version_id=?', v2.id)[0];
    assert.equal(feedback.decision, null, 'Changed version must require fresh review');
    const inspections = [], plans = [], pcm = [], audioData = [], pictures = [];
    for (const v of versions) {
      assert.equal(digest(await readFile(v.media)), v.sha256, 'Published media changed');
      assert.equal(digest(await readFile(v.nativeCheckpoint)), v.nativeFingerprint, 'Native checkpoint changed');
      if (v.planSha256) assert.equal(digest(await readFile(v.planPath)), v.planSha256, 'Published plan changed');
      if (v.receiptSha256) assert.equal(digest(await readFile(v.receiptPath)), v.receiptSha256, 'Published receipt changed');
      if (v.inspectionSha256) assert.equal(digest(await readFile(v.inspectionPath)), v.inspectionSha256, 'Published inspection changed');
      const receipt = await json(v.receiptPath);
      assert.equal(receipt.backend, f.project.backend); assert.equal(receipt.jobId, v.jobId);
      assert.equal(receipt.nativeRendered, true);
      assert.deepEqual(receipt.expected, { frames: expectedFrames, width: expectedWidth, height: expectedHeight, fps: '25/1' });
      const result = await json(path.join(f.project.root, '10_WORK', 'jobs', v.jobId, 'result.json'));
      assert.deepEqual(result.versionIds, [v.id]); assert.equal(result.jobId, v.jobId);
      const probe = JSON.parse(run('ffprobe', ['-v', 'error', '-count_frames', '-show_streams', '-of', 'json', v.media]));
      const video = probe.streams.filter(s => s.codec_type === 'video');
      assert.equal(video.length, 1); assert.equal(video[0].nb_read_frames, String(expectedFrames));
      assert.equal(video[0].width, expectedWidth); assert.equal(video[0].height, expectedHeight); assert.equal(video[0].r_frame_rate, '25/1');
      assert.equal(probe.streams.filter(s => s.codec_type === 'audio').length, 1);
      const decodedAudio = run('ffmpeg', ['-v', 'error', '-i', v.media, '-map', '0:a:0', '-f', 'f32le', '-']);
      audioData.push(decodedAudio); pcm.push(digest(decodedAudio));
      pictures.push(digest(run('ffmpeg', ['-v', 'error', '-i', v.media, '-map', '0:v:0', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'])));
      inspections.push(await json(v.inspectionPath || path.join(path.dirname(v.receiptPath), 'inspection.json')));
      plans.push(await json(v.planPath));
      if (tracking || panels) {
        const framing = plans.at(-1).framing;
        assert.equal(digest(await readFile(framing.receiptPath)), framing.receiptSha256,
          'Framing decision receipt changed');
      }
    }
    const failures = [];
    if (pcm[0] !== pcm[1]) failures.push('Finishing revision changed decoded audio; exact-audio qualification failed');
    assert.equal(audioData[0].length, audioData[1].length, 'Decoded audio length changed');
    let signalEnergy = 0, differenceEnergy = 0, maxDifference = 0;
    for (let i = 0; i < audioData[0].length; i += 4) {
      const a = audioData[0].readFloatLE(i), b = audioData[1].readFloatLE(i), difference = b - a;
      assert(Number.isFinite(a) && Number.isFinite(b), 'Nonfinite audio sample');
      signalEnergy += a * a; differenceEnergy += difference * difference;
      maxDifference = Math.max(maxDifference, Math.abs(difference));
    }
    assert.notEqual(pictures[0], pictures[1], 'Revision produced identical pictures');
    let panelEvidence=null;
    if(panels){panelEvidence=JSON.parse(run(f.config.python,[path.resolve('scripts/panel_agent_fixture.py'),'check',path.join(base,'fixture.json'),JSON.stringify(versions)]));}
    else if(tracking){
      assert.equal(plans[0].framing.shots['cut-0'].mode,'tracked-crop');
      assert.deepEqual(plans[1].framing.shots['cut-0'].xByFrame,Array.from({length:25},(_,i)=>80.25+i));
      assert.equal(plans[1].framing.shots['cut-0'].x,80.25);
      assert.notEqual(plans[1].framing.receiptSha256,plans[0].framing.receiptSha256);
      const adjusted=structuredClone(plans[1]);adjusted.framing.receiptPath=plans[0].framing.receiptPath;adjusted.framing.receiptSha256=plans[0].framing.receiptSha256;
      adjusted.framing.shots['cut-0'].x=plans[0].framing.shots['cut-0'].x;adjusted.framing.shots['cut-0'].xByFrame=plans[0].framing.shots['cut-0'].xByFrame;
      assert.deepEqual(adjusted,plans[0],'Tracking revision changed another plan field');
    }else{
      assert.equal(plans[0].captions[0].text, 'NATIVE AGENT LOOP');
      assert.equal(plans[1].captions[0].text, 'REVISED AGENT LOOP');
      plans[1].captions[0].text = plans[0].captions[0].text;
      assert.deepEqual(plans[1], plans[0], 'Caption wording revision changed other plan fields');
    }
    if (f.project.backend === 'filmcraft') {
      if(panels){assert(panelEvidence.nativeGraph.includes('protected saved project preserved'));}
      else if(tracking){
        const data=await Promise.all(versions.map(v=>json(v.nativeCheckpoint)));
        assert.equal(data[1].view.active_sequence,data[0].view.active_sequence,'Active native sequence changed');
        assert.equal(data[1].project.name,path.basename(v2.nativeProject,'.fcproj'));
        assert.equal(data[1].project.root.name,data[1].project.name);
        data[0].project.name=data[1].project.name;data[0].project.root.name=data[1].project.root.name;
        const frameTicks=254016000000/25;
        for(let versionIndex=0;versionIndex<data.length;versionIndex++){
          const d=data[versionIndex];
          const sequence=d.project.items[String(d.view.active_sequence)].kind.Sequence;
          const shot=plans[versionIndex].framing.shots['cut-0'];
          const nativeAnchor=sequence.video_tracks[0].items[0].effects.find(e=>e.effect==='motion').params.anchor;
          assert.equal(nativeAnchor.keyframes.length,25);
          assert.deepEqual(nativeAnchor.value,{Vec2:{x:shot.x+shot.width/2,y:shot.y+shot.height/2}});
          nativeAnchor.keyframes.forEach((key,i)=>{
            assert.equal(key.time,(plans[versionIndex].cuts[0].sourceInFrame+i)*frameTicks);
            assert.equal(key.interp,'Linear');
            assert.deepEqual(key.value,{Vec2:{x:shot.xByFrame[i]+shot.width/2,y:shot.y+shot.height/2}});
          });
          const anchor=sequence.video_tracks[0].items[0].effects.find(e=>e.effect==='motion').params.anchor;
          delete anchor.value;delete anchor.keyframes;
        }
        assert.deepEqual(data[1].project,data[0].project,'Tracking changed protected saved native data');
        const v1cut=inspections[0].video[0].items[0],v2cut=inspections[1].video[0].items[0];
        const m1=v1cut.effects.find(e=>e.effect==='motion').params,m2=v2cut.effects.find(e=>e.effect==='motion').params;
        assert.equal(m1.anchor.keyframes,25);assert.equal(m2.anchor.keyframes,25);
      }else{
        const native1 = JSON.stringify(inspections[0]), native2 = JSON.stringify(inspections[1]);
        assert(native1.includes('NATIVE AGENT LOOP') && native2.includes('REVISED AGENT LOOP'));
        assert.equal(native2.replaceAll('REVISED AGENT LOOP', 'NATIVE AGENT LOOP'), native1,
          'Native state changed beyond caption wording');
      }
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
    if(panels){
      const request=await json(path.join(base,'revision-request.json')),submitted=jobs[1].snapshot[0];
      assert.equal(submitted.feedback.notes,request.notes,'Submitted panel notes changed');
      assert.equal(submitted.feedback.comments[0].text,request.comment,'Submitted panel comment changed');
      assert.equal(pending[0].latest.comments[1].text,request.lateComment,'Late panel comment changed');
      assert(submitted.owners.includes('assembly-design')&&submitted.owners.includes('horizontal-to-vertical'),'Panel feedback missed its capability owners');
    }

    console.log(JSON.stringify({ passed: failures.length === 0, failures, scope: `synthetic ${f.project.backend} ${f.scenario||'caption'} agent/review integration, not editorial approval`,
      agent: f.project.agent, nativeJobs: jobs.length, versions: versions.map(v => v.id),
      sourceAndPublishedHashesPreserved: true, archivedArtifactsPinned: Boolean(archivedArtifactsPinned), nativeChange: f.project.backend === 'filmcraft' ? (panels?'selected panels only; protected saved native project data preserved':tracking?'selected X curve only; protected saved native project data preserved':'caption text only') : 'finishing plan changed; native cuts/sources/properties/links preserved; Fusion appearance requires inspection',
      ...(panelEvidence?{panelEvidence}:{}), decodedAudioIdentical: pcm[0] === pcm[1],
      audioDifference: {maxSampleDifference: maxDifference, rmsRelativeDb: differenceEnergy && signalEnergy ? 10 * Math.log10(differenceEnergy / signalEnergy) : null},
      renderedPicturesChanged: true, lateCommentPreserved: true }, null, 2));
    if (failures.length) process.exitCode = 1;
  } finally { db.close(); }
}
