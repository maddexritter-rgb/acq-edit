import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'distribution/skills/find-precedents/scripts'))
from test_editorial_context import EditorialContextTests
from editorial_context import fetch_context,BrainUnavailable

class TeamReader(EditorialContextTests):
    def test_dedicated_gateway_preserves_full_query_and_validation(self):
        with patch.dict('os.environ',{'EDITORIAL_BRAIN_FUNCTION_URL':'https://projectref.supabase.co/functions/v1/vibe-editorial-read'}),patch('urllib.request.build_opener') as opener:
            opener.return_value.open.return_value=self.response(required_reading=True)
            result=fetch_context(problem='assembly preflight',fmt='q_and_a',required_reading=True)
            self.assertEqual(len(result['required_reading']['policies']),2)
            request=opener.return_value.open.call_args.args[0]
            self.assertEqual(json.loads(request.data)['limit'],5)
            handler=opener.call_args.args[0]
            self.assertIsNone(handler.redirect_request(None,None,302,None,None,'https://elsewhere.test'))
    def test_gateway_host_and_url_suffix_are_not_sufficient(self):
        for url in ['https://projectref.evil.test/functions/v1/vibe-editorial-read','https://projectref.supabase.co/functions/v1/vibe-editorial-read?token=x','https://projectref.supabase.co:444/functions/v1/vibe-editorial-read']:
            with patch.dict('os.environ',{'EDITORIAL_BRAIN_FUNCTION_URL':url}),patch('urllib.request.build_opener') as opener:
                with self.assertRaises(BrainUnavailable):fetch_context(problem='question context',fmt='q_and_a')
                opener.assert_not_called()

if __name__=='__main__':unittest.main()
