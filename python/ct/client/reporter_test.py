#!/usr/bin/env python
import unittest

from collections import defaultdict
from ct.cert_analysis import asn1
from ct.cert_analysis import base_check_test
from ct.client import reporter
from ct.client.db import sqlite_cert_db
from ct.client.db import sqlite_connection as sqlitecon
from ct.crypto import cert
from ct.proto import certificate_pb2
from ct.proto import client_pb2

STRICT_DER = cert.Certificate.from_der_file(
                    'ct/crypto/testdata/google_cert.der', False).to_der()
NON_STRICT_DER = cert.Certificate.from_pem_file(
                    'ct/crypto/testdata/invalid_ip.pem', False).to_der()

class FakeCheck(object):
    @staticmethod
    def check(certificate):
        return [asn1.Strict("Boom!")]

class CertificateReportTest(base_check_test.BaseCheckTest):
    class CertificateReportBase(reporter.CertificateReport):
        def __init__(self, checks):
            super(CertificateReportTest.CertificateReportBase, self).__init__(
                    checks=checks)

        def certs(self):
            return self._certs

        def report(self):
            super(CertificateReportTest.CertificateReportBase, self).report()
            return self.observations

        def reset(self):
            self._certs = {}
            self.observations = defaultdict(list)

        def _batch_scanned_callback(self, result):
            for desc, log_index, observations in result:
                self._certs[log_index] = desc
                self.observations[log_index] += observations

    class FakeCheck(object):
        @staticmethod
        def check(certificate):
            return [asn1.Strict("Boom!")]

    def setUp(self):
        self.cert_db = sqlite_cert_db.SQLiteCertDB(
                sqlitecon.SQLiteConnectionManager(":memory:", keepalive=True))

    def test_scan_der_cert_no_checks(self):
        report = self.CertificateReportBase([])
        report.scan_der_certs([(0, STRICT_DER, [''], client_pb2.X509_ENTRY)])
        result = report.report()
        self.assertEqual(len(sum(result.values(), [])), 0)

    def test_scan_der_cert_broken_cert(self):
        report = self.CertificateReportBase([])
        report.scan_der_certs([(0, "asdf", [''], client_pb2.X509_ENTRY)])
        result = report.report()
        self.assertObservationIn(asn1.All(),
                      sum(result.values(), []))
        self.assertEqual(len(sum(result.values(), [])), 1)

    def test_scan_der_cert_check(self):
        report = self.CertificateReportBase([FakeCheck()])
        report.scan_der_certs([(0, STRICT_DER, [''], client_pb2.X509_ENTRY)])
        result = report.report()

        self.assertObservationIn(asn1.Strict("Boom!"),
                                 sum(result.values(), []))
        self.assertEqual(len(result), 1)

    def test_scan_der_cert_check_non_strict(self):
        report = self.CertificateReportBase([FakeCheck()])
        report.scan_der_certs([(0, NON_STRICT_DER, [''], client_pb2.X509_ENTRY)])
        result = report.report()
        # There should be FakeCheck and asn.1 strict parsing failure
        self.assertEqual(len(sum(result.values(), [])), 2)
        self.assertObservationIn(asn1.Strict("Boom!"), sum(result.values(), []))

    def test_entry_type_propogated(self):
        report = self.CertificateReportBase([])
        report.scan_der_certs([(0, STRICT_DER, [''], client_pb2.PRECERT_ENTRY),
                               (1, STRICT_DER, [''], client_pb2.X509_ENTRY)])
        result = report.report()
        self.assertEqual(len(sum(result.values(), [])), 0)

        certs = report.certs()
        self.assertEqual(len(certs), 2)
        self.assertEquals(certs[0].entry_type, client_pb2.PRECERT_ENTRY)
        self.assertEquals(certs[1].entry_type, client_pb2.X509_ENTRY)

if __name__ == '__main__':
    unittest.main()
