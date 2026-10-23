/** Bounded parser for the exact project-metadata shape observed on 26.3.
 * This is readback evidence, not a public promise about other metadata formats.
 * Unknown namespaces, duplicate fields and disagreement fail closed.
 */
export const AUDIO_SOURCE_CLOCK = String.raw`
function audioSourceOffset(item){
  if(!item||typeof item.getProjectMetadata!=='function')throw new Error('SOURCE_CLOCK_METADATA_UNAVAILABLE');
  var xml=String(item.getProjectMetadata());
  if(xml.length>1048576||xml.indexOf('<!DOCTYPE')>=0||xml.indexOf('<!ENTITY')>=0||xml.indexOf('xmlns:premierePrivateProjectMetaData="http://ns.adobe.com/premierePrivateProjectMetaData/1.0/"')<0)throw new Error('SOURCE_CLOCK_METADATA_FORMAT_UNSUPPORTED');
  function offset(label){
    var tag='premierePrivateProjectMetaData:Column.Intrinsic.'+label;
    var open=xml.indexOf('<'+tag+' '),plain=xml.indexOf('<'+tag+'>');
    if(open<0)open=plain;else if(plain>=0)throw new Error('SOURCE_CLOCK_METADATA_AMBIGUOUS');
    if(open<0||xml.indexOf('<'+tag+' ',open+1)>=0||xml.indexOf('<'+tag+'>',open+1)>=0)throw new Error('SOURCE_CLOCK_METADATA_AMBIGUOUS');
    var begin=xml.indexOf('>',open),end=xml.indexOf('</'+tag+'>',begin),block=xml.substring(begin+1,end);
    if(begin<0||end<begin)throw new Error('SOURCE_CLOCK_METADATA_MALFORMED');
    var values=block.match(/<premierePrivateProjectMetaData:offset>(0|[1-9][0-9]{0,18})<\/premierePrivateProjectMetaData:offset>/g);
    if(!values||values.length!==1)throw new Error('SOURCE_CLOCK_OFFSET_UNAVAILABLE');
    return values[0].replace(/<[^>]+>/g,'');
  }
  var a=offset('AudioInPoint'),b=offset('AudioOutPoint');
  if(a!==b||a.length===19&&a>'9223372036854775807')throw new Error('SOURCE_CLOCK_OFFSETS_DISAGREE');
  return a;
}
`;
