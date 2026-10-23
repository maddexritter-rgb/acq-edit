export function packSnapshot(value: unknown) {
 const nodes: unknown[][]=[],seen=new Map<string,number>();
 function put(x: unknown): number {
  let node: unknown[];
  if(x===null)node=['z'];
  else if(typeof x==='boolean')node=['b',x];
  else if(typeof x==='number'){if(!Number.isFinite(x))throw Error('NON_JSON_SNAPSHOT');node=['n',Object.is(x,-0)?0:x];}
  else if(typeof x==='string')node=['s',x];
  else if(Array.isArray(x))node=['a',x.map(put)];
  else if(typeof x==='object' && Object.getPrototypeOf(x)===Object.prototype){
   node=['o',Object.keys(x).map(k=>{if(['__proto__','constructor','prototype'].includes(k))throw Error('UNSAFE_SNAPSHOT_KEY');return[put(k),put((x as Record<string, unknown>)[k])];})];
  }else throw Error('NON_JSON_SNAPSHOT');
  const key=JSON.stringify(node);if(seen.has(key))return seen.get(key)!;
  const id=nodes.length;nodes.push(node);seen.set(key,id);return id;
 }
 const root=put(value);return {schema:1,root,nodes};
}
export const SNAPSHOT_UNPACK = `function __unpackSnapshot(p){
 if(!p||p.schema!==1||Object.prototype.toString.call(p.nodes)!=='[object Array]')throw Error('INVALID_PACKED_SNAPSHOT');
 var memo=[],done=[];
 function get(id){
  if(typeof id!=='number'||id%1!==0||id<0||id>=p.nodes.length)throw Error('INVALID_SNAPSHOT_REFERENCE');
  if(done[id])return memo[id];var n=p.nodes[id],v,i,k;
  if(!n||Object.prototype.toString.call(n)!=='[object Array]')throw Error('INVALID_SNAPSHOT_NODE');
  if(n[0]==='z'&&n.length===1)v=null;
  else if(n[0]==='b'&&n.length===2&&typeof n[1]==='boolean')v=n[1];
  else if(n[0]==='n'&&n.length===2&&typeof n[1]==='number'&&isFinite(n[1]))v=n[1];
  else if(n[0]==='s'&&n.length===2&&typeof n[1]==='string')v=n[1];
  else if(n[0]==='a'&&n.length===2&&Object.prototype.toString.call(n[1])==='[object Array]'){
   v=[];for(i=0;i<n[1].length;i++){if(n[1][i]>=id)throw Error('NON_TOPOLOGICAL_SNAPSHOT');v.push(get(n[1][i]));}
  }else if(n[0]==='o'&&n.length===2&&Object.prototype.toString.call(n[1])==='[object Array]'){
   v={};for(i=0;i<n[1].length;i++){var pair=n[1][i];if(!pair||pair.length!==2||pair[0]>=id||pair[1]>=id)throw Error('INVALID_SNAPSHOT_PAIR');k=get(pair[0]);if(typeof k!=='string'||k==='__proto__'||k==='constructor'||k==='prototype'||Object.prototype.hasOwnProperty.call(v,k))throw Error('INVALID_SNAPSHOT_KEY');v[k]=get(pair[1]);}
  }else throw Error('INVALID_SNAPSHOT_NODE');
  done[id]=true;memo[id]=v;return v;
 }return get(p.root);
}`;
