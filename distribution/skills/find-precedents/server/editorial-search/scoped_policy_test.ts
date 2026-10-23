import { parseSearchRequest } from './search_core.ts';
import handler from './index.ts';

function assert(value: unknown, message='assertion failed'): asserts value { if (!value) throw new Error(message); }
Deno.test('legacy request shape is unchanged', () => {
  const p=parseSearchRequest({problem:'opening context',format:'q_and_a'});
  assert(!('brand' in p));assert(!('productionType' in p));assert(!('stage' in p));
});
Deno.test('production scope is independent of answer-only format', () => {
  const p=parseSearchRequest({problem:'opening context',format:'monologue',brand:'brand_x',production_type:'l1_short',stage:'assembly'});
  assert(p.format==='monologue' && p.brand==='brand_x' && p.productionType==='l1_short' && p.stage==='assembly');
});
Deno.test('partial scope and unsupported stage refused', () => {
  for(const extra of [{brand:'brand_x'},{stage:'assembly'},{brand:'brand_x',production_type:'l1_short',stage:'unknown'}]) {
    let failed=false;try{parseSearchRequest({problem:'opening context',...extra});}catch{failed=true;}assert(failed);
  }
});
Deno.test('authorization still precedes database access', async () => {
  const response=await handler.fetch(new Request('https://example.test',{method:'POST',body:'{}'}));
  assert(response.status===401);
});
Deno.test('scoped database failure preserves core format response', async () => {
  const keys=['EDITORIAL_BRAIN_READ_TOKEN','SUPABASE_URL','SUPABASE_SERVICE_ROLE_KEY'];
  const before=keys.map(k=>Deno.env.get(k));const prior=globalThis.fetch;
  try {
    Deno.env.set(keys[0],'test-only-read-token-01234567890123456789');
    Deno.env.set(keys[1],'https://projectref.supabase.co');Deno.env.set(keys[2],'test-only-database-key');
    globalThis.fetch=async (url) => String(url).endsWith('/editorial_context_search') ?
      Response.json({playbooks:[{format:'universal'},{format:'monologue'}],cards:[]}) : new Response('',{status:503});
    const response=await handler.fetch(new Request('https://example.test',{method:'POST',
      headers:{Authorization:'Bearer test-only-read-token-01234567890123456789'},
      body:JSON.stringify({problem:'opening context',format:'monologue',brand:'brand_x',production_type:'l1_short'})}));
    const body=await response.json();assert(response.status===200);assert(body.scoped_policy.status==='unavailable');
    assert(body.playbooks.length===2 && body.cards.length===0);
  } finally {
    globalThis.fetch=prior;keys.forEach((k,i)=>before[i]===undefined?Deno.env.delete(k):Deno.env.set(k,before[i]!));
  }
});
