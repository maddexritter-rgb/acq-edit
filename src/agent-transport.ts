import { spawn } from 'node:child_process';
import { createInterface } from 'node:readline';
import type { Agent } from './contracts.js';

export interface AgentTransport {
  agent: Agent;
  command: string;
  args: string[];
  cwd: string;
  env: NodeJS.ProcessEnv;
  session?: string | null;
  prompt: string;
  writableRoots: string[];
  onSession: (id: string) => void;
  onLine: (line: string) => Promise<unknown>;
  signal?: AbortSignal;
  timeoutMs?: number;
  requestTimeoutMs?: number;
  shutdownGraceMs?: number;
}

/** Own only the spawned agent process group; never kill an editor host. */
export async function runAgentTransport(o: AgentTransport): Promise<void> {
  o.signal?.throwIfAborted();
  if (o.timeoutMs !== undefined && (!Number.isSafeInteger(o.timeoutMs) || o.timeoutMs < 1)) throw new Error('Agent timeout must be a positive integer');
  await new Promise<void>((resolve, reject) => {
    const child = spawn(o.command, o.args, {
      cwd: o.cwd, env: o.env, detached: process.platform !== 'win32',
      stdio: ['pipe', 'pipe', 'pipe'],
    });
    let stopping = false, closed = false, failure: Error | undefined;
    let stderr = '', protocolDone = false, logWrites = Promise.resolve();
    let thread = '', turn = '', nextId = 0, claudeResult = false;
    const earlyCompletions: any[] = [];
    const pending = new Map<number, { resolve: (v: any) => void; reject: (e: Error) => void; timer: NodeJS.Timeout }>();
    let killTimer: NodeJS.Timeout | undefined;
    const signalGroup = (signal: NodeJS.Signals) => {
      if (!child.pid) return;
      try {
        if (process.platform === 'win32') child.kill(signal);
        else process.kill(-child.pid, signal);
      } catch (e: any) { if (e.code !== 'ESRCH') failure ||= e; }
    };
    const stop = (error?: Error) => {
      failure ||= error;
      if (stopping || closed) return;
      stopping = true;
      for (const p of pending.values()) {
        clearTimeout(p.timer); p.reject(error || new Error('Agent transport closing'));
      }
      pending.clear();
      child.stdin.end();
      signalGroup('SIGTERM');
      killTimer = setTimeout(() => signalGroup('SIGKILL'), o.shutdownGraceMs ?? 5000);
    };
    const abort = () => stop(new Error('Agent interrupted by service shutdown; inspect native state before recovery'));
    const deadline = setTimeout(() => stop(new Error('Agent job deadline exceeded; inspect native state before retrying')), o.timeoutMs ?? 6 * 3600_000);
    o.signal?.addEventListener('abort', abort, { once: true });
    const send = (method: string, params: unknown) => new Promise<any>((resolve, reject) => {
      if (stopping || closed) { reject(new Error('Agent is closing')); return; }
      const id = ++nextId;
      const timer = setTimeout(() => stop(new Error(`Codex request timed out: ${method}`)), o.requestTimeoutMs ?? 60_000);
      pending.set(id, { resolve, reject, timer });
      child.stdin.write(JSON.stringify({ id, method, params }) + '\n');
    });
    const completeTurn = (params: any) => {
      if (params.threadId !== thread || params.turn?.id !== turn) return;
      if (params.turn.status !== 'completed') {
        stop(new Error(`Codex turn ${params.turn.status}: ${params.turn.error?.message || 'inspect agent log'}`));
      } else { protocolDone = true; stop(); }
    };
    child.stdin.on('error', e => { if (!stopping) stop(e); });
    child.stderr.on('data', b => { stderr = (stderr + b).slice(-4000); });
    child.on('error', e => stop(e));
    const lines = createInterface({ input: child.stdout });
    lines.on('line', line => {
      logWrites = logWrites.then(() => o.onLine(line)).then(() => {}).catch(e => { stop(e); });
      if (stopping) return;
      try {
        const m = JSON.parse(line);
        if (o.agent === 'claude') {
          if (typeof m.session_id === 'string' && m.session_id) {
            if ((o.session && m.session_id !== o.session) || (thread && m.session_id !== thread)) throw new Error('Claude returned a different session');
            if (!thread) { thread = m.session_id; o.onSession(thread); }
          }
          if (m.type === 'result') {
            claudeResult = true;
            if (m.is_error || m.subtype !== 'success') {
              stop(new Error(`Claude result ${m.is_error ? 'error' : m.subtype || 'error'}: ${m.result || (m.errors || []).join('; ') || 'inspect agent log'}`));
            } else {
              if (!thread || m.session_id !== thread) throw new Error('Claude result has no matching session');
              protocolDone = true;
            }
          }
          return;
        }
        if (m.id !== undefined && m.method) {
          child.stdin.write(JSON.stringify({ id: m.id, error: { code: -32000, message: 'Interactive input required; inspect this job before resuming' } }) + '\n');
          stop(new Error(`Codex requires interactive input (${m.method}); see agent log`));
          return;
        }
        if (m.id !== undefined) {
          const p = pending.get(m.id);
          if (p) { pending.delete(m.id); clearTimeout(p.timer); m.error ? p.reject(new Error(m.error.message)) : p.resolve(m.result); }
        }
        if (m.method === 'turn/completed' && m.params?.threadId === thread) {
          // A very short turn can complete before the start response continuation runs.
          if (!turn) earlyCompletions.push(m.params); else completeTurn(m.params);
        }
      } catch (e) { stop(new Error('Invalid agent event: ' + (e as Error).message)); }
    });
    child.on('close', async code => {
      closed = true;
      clearTimeout(deadline); if (killTimer) clearTimeout(killTimer);
      o.signal?.removeEventListener('abort', abort);
      for (const p of pending.values()) { clearTimeout(p.timer); p.reject(new Error('Agent disconnected')); }
      pending.clear();
      await logWrites;
      if (!failure && !protocolDone) failure = new Error(o.agent === 'claude' && !claudeResult
        ? 'Claude exited without a completion result; inspect receipts'
        : 'Codex disconnected before exact turn completion; inspect receipts');
      if (!failure && o.agent === 'claude' && code !== 0) failure = new Error(`Claude exited ${code}: ${stderr}`);
      failure ? reject(failure) : resolve();
    });
    if (o.agent === 'claude') child.stdin.end();
    else void (async () => {
      await send('initialize', { clientInfo: { name: 'acq-edit', version: '0.1.0' }, capabilities: {} });
      child.stdin.write(JSON.stringify({ method: 'initialized' }) + '\n');
      const settings = { cwd: o.cwd, approvalPolicy: 'on-request', sandbox: 'workspace-write' };
      const response = o.session
        ? await send('thread/resume', { threadId: o.session, ...settings })
        : await send('thread/start', settings);
      thread = response.thread.id;
      if (typeof thread !== 'string' || !thread || (o.session && thread !== o.session)) throw new Error('Codex returned a different or missing session');
      o.onSession(thread);
      const started = await send('turn/start', {
        threadId: thread, cwd: o.cwd,
        sandboxPolicy: { type: 'workspaceWrite', writableRoots: o.writableRoots, networkAccess: true },
        input: [{ type: 'text', text: o.prompt, text_elements: [] }],
      });
      turn = started.turn.id;
      if (typeof turn !== 'string' || !turn) throw new Error('Codex returned no turn ID');
      for (const event of earlyCompletions) completeTurn(event);
    })().catch(e => { if (!closed && !stopping) stop(e); });
    if (o.signal?.aborted) abort();
  });
}
