import test from 'node:test';
import assert from 'node:assert/strict';
import { chatLayout } from './chatLayout.mjs';
const attachments = [{ reference_label:'V1', element_id:'image-00001' }, { reference_label:'V2', element_id:'table-00002' }];
test('places only authorised originals once and leaves unplaced originals available', () => {
 const result = chatLayout('Find it.\n\nCheck it.', [
  {text:'Find it.',reference_labels:['V1','V99','V1']}, {text:'Check it.',reference_labels:['V1']}
 ],attachments);
 assert.deepEqual(result.sections[0].attachments,[attachments[0]]);
 assert.deepEqual(result.sections[1].attachments,[]);
 assert.deepEqual(result.remainingAttachments,[attachments[1]]);
});
test('invalid and old layouts preserve the entire plain answer and originals', () => {
 for(const sections of [undefined,[],[{text:'Altered'}],[{text:''}]]) {
  assert.deepEqual(chatLayout('Answer',sections,attachments),{sections:[],remainingAttachments:attachments});
 }
});
test('revoked originals do not erase text',()=>{
 const result=chatLayout('Answer',[{text:'Answer',reference_labels:['V1']}],[]);
 assert.equal(result.sections[0].text,'Answer');
 assert.deepEqual(result.sections[0].attachments,[]);
});
