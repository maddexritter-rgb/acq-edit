import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import skill_dependencies as dependencies
import materialize


class DependencyTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name)
        self.files={'edit/SKILL.md':'Use skill: [text-hook](../text-hook/SKILL.md)',
                    'text-hook/SKILL.md':'Use skill: [slop-detector](../slop-detector/SKILL.md)',
                    'slop-detector/SKILL.md':'Preserve the supplied meaning.'}
        self.policy={'externalRoutes':[]}
        (self.root/'docs').mkdir();(self.root/'docs/AGENT_WORKFLOW.md').write_text('Fixed backend execution')

    def write(self):
        entries=[]
        for name,text in self.files.items():
            p=self.root/'distribution/skills'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text)
            entries.append({'path':name,'distribution_sha256':hashlib.sha256(text.encode()).hexdigest()})
        manifest={'schema':'acq-edit/source-manifest-v1','owners':[str(Path(name).parent) for name in self.files if name.endswith('/SKILL.md')],'files':entries}
        (self.root/'distribution/SOURCE_MANIFEST.json').write_text(json.dumps(manifest))
        p=self.root/dependencies.POLICY;p.parent.mkdir(exist_ok=True);p.write_text(json.dumps(self.policy))

    def seal(self):
        self.write();result=dependencies.inventory(self.root)
        (self.root/dependencies.INVENTORY).write_text(json.dumps(result))
        return result

    def test_required_transitive_owner_is_packaged_and_pinned_in_runtime(self):
        inventory=self.seal();self.assertEqual(len(inventory['edges']),2)
        self.assertTrue(all(e['status']=='packaged' for e in inventory['edges']))
        materialize.materialize(self.root,self.root/'assets')
        receipt=json.loads((self.root/'.local/skills/.acq-materialization.json').read_text())
        self.assertEqual(receipt['dependencies']['packagedOwners'],3)
        self.assertEqual(receipt['dependencies']['explicitRoutes'],2)
        self.assertIn('slop-detector/SKILL.md',receipt['files'])

    def test_missing_required_owner_stops_before_runtime_creation(self):
        del self.files['slop-detector/SKILL.md'];self.write()
        with self.assertRaisesRegex(ValueError,'Unclassified missing.*slop-detector'):
            dependencies.inventory(self.root)
        with self.assertRaisesRegex(ValueError,'Unclassified missing'):
            materialize.materialize(self.root,self.root/'assets')
        self.assertFalse((self.root/'.local').exists())

    def test_optional_exception_is_scoped_to_exact_source_and_becomes_stale(self):
        self.files['slop-detector/SKILL.md']='For Slack only: Use skill: slack-voice.'
        self.policy['externalRoutes']=[{'source':'slop-detector/SKILL.md','target':'slack-voice','status':'external-opt-in','reason':'Conditional Slack drafting only'}]
        self.seal()
        result=dependencies.verify(self.root);self.assertEqual(result['externalRoutes'][0]['target'],'slack-voice')
        self.files['text-hook/SKILL.md']+='\nUse skill: slack-voice';self.write()
        with self.assertRaisesRegex(ValueError,'Unclassified missing.*text-hook'):
            dependencies.inventory(self.root)
        self.files['text-hook/SKILL.md']='No reference';self.files['slop-detector/SKILL.md']='No reference';self.write()
        with self.assertRaisesRegex(ValueError,'Stale external route'):
            dependencies.inventory(self.root)

    def test_changed_routes_or_policy_fail_inventory_verification(self):
        self.seal();self.files['edit/SKILL.md']+='\nUse skill: slop-detector';self.write()
        with self.assertRaisesRegex(ValueError,'inventory is stale'):
            dependencies.verify(self.root)
        self.seal();self.policy['reviewNote']='Changed policy revision';self.write()
        with self.assertRaisesRegex(ValueError,'inventory is stale'):
            dependencies.verify(self.root)
        self.seal();p=self.root/'distribution/skills/text-hook/SKILL.md';p.write_text('unrecorded edit')
        with self.assertRaisesRegex(ValueError,'hash differs'):
            dependencies.verify(self.root)


if __name__=='__main__':unittest.main()
