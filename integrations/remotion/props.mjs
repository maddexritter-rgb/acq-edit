export const defaults={text:'A clear idea.',accent:'#b4caff',font:'Arial',size:96,enterFrames:12,exitFrames:8,transparent:true,frames:90,width:1080,height:1920,fps:30};
export function resolveProps(input){
 if(!input||typeof input!=='object'||Array.isArray(input)||Object.keys(input).some(k=>!Object.hasOwn(defaults,k)))throw Error('Unsupported motion properties');
 const p={...defaults,...input};
 for(const k of ['width','height','frames','enterFrames','exitFrames'])if(!Number.isSafeInteger(p[k])||p[k]<=0)throw Error(`Invalid ${k}`);
 if(p.width<256||p.height<256||p.exitFrames<2||p.enterFrames+p.exitFrames>p.frames)throw Error('Unsupported canvas or overlapping animation ranges');
 if(!Number.isFinite(p.fps)||p.fps<=0||!Number.isFinite(p.size)||p.size<=0)throw Error('Invalid frame rate or font size');
 if(typeof p.text!=='string'||!p.text.trim()||typeof p.font!=='string'||!p.font.trim()||typeof p.accent!=='string'||!/^#[0-9a-f]{6}$/i.test(p.accent))throw Error('Explicit text, local font and six-digit accent required');
 if(p.transparent!==true)throw Error('Motion assets must have a transparent canvas');
 return p;
}
