import os
from pathlib import Path
import ssl
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from runtime_environment import trusted_environment,select_node,execution_environment

class Runtime(unittest.TestCase):
    def test_missing_explicit_company_bundle_fails_without_disabling_tls(self):
        with self.assertRaisesRegex(ValueError,'SSL_CERT_FILE'):
            trusted_environment({'SSL_CERT_FILE':'/missing-company-ca'})
    def test_system_ca_repairs_missing_default_and_propagates_to_node_pip(self):
        result=trusted_environment({})
        self.assertEqual(result['SSL_CERT_FILE'],'/etc/ssl/cert.pem')
        self.assertEqual(result['NODE_EXTRA_CA_CERTS'],result['SSL_CERT_FILE'])
        self.assertEqual(result['PIP_CERT'],result['SSL_CERT_FILE'])
        self.assertNotIn('NODE_TLS_REJECT_UNAUTHORIZED',result)
    def test_explicit_company_certificate_preserved(self):
        ca='/etc/ssl/cert.pem'
        result=trusted_environment({'SSL_CERT_FILE':ca,'NODE_EXTRA_CA_CERTS':ca})
        self.assertEqual(result['SSL_CERT_FILE'],ca)
    def test_empty_trust_is_actionable(self):
        with patch('runtime_environment.ssl.create_default_context') as ctx:
            ctx.return_value.get_ca_certs.return_value=[]
            with self.assertRaisesRegex(ValueError,'No trusted CA'):trusted_environment({},Path('/missing-ca'))
    def test_broken_explicit_node_is_not_silently_replaced(self):
        with tempfile.TemporaryDirectory() as d:
            node=Path(d)/'node';node.write_text('#!/bin/sh\nexit 1\n');node.chmod(0o755)
            with self.assertRaisesRegex(ValueError,'No working Node'):select_node({'ACQ_EDIT_NODE':str(node)})
    def test_verified_node_path_is_propagated(self):
        with tempfile.TemporaryDirectory() as d:
            node=Path(d)/'node';node.write_text('#!/bin/sh\necho v24.1.0\n');node.chmod(0o755)
            env=execution_environment({'ACQ_EDIT_NODE':str(node),'PATH':'/usr/bin'})
            self.assertEqual(env['ACQ_EDIT_NODE'],str(node.resolve()))
            self.assertTrue(env['PATH'].startswith(str(node.resolve().parent)+os.pathsep))
if __name__=='__main__':unittest.main()
