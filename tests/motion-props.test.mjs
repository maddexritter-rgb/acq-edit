import test from 'node:test';
import assert from 'node:assert/strict';
import {resolveProps,defaults} from '../integrations/remotion/props.mjs';
test('motion parameters resolve defaults and reject invalid animation intervals or unsupported effects',()=>{
 assert.deepEqual(resolveProps({text:'New title'}),{...defaults,text:'New title'});
 for(const value of [null,[],{enterFrames:0},{exitFrames:1},{frames:10},{width:10},{height:1.5},{fps:0},{fps:Infinity},{text:''},{font:''},{transparent:false},{size:-1},{accent:'red'},{effect:'unknown'}])assert.throws(()=>resolveProps(value));
 assert.equal(resolveProps({frames:25,enterFrames:5,exitFrames:5,fps:25,width:640,height:360}).frames,25);
});
