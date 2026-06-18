import json

import frappe

from lms.lms.test_helpers import BaseTestUtils
from lms.lms.verifiable_credentials import issue_credential_for_certificate, verify_credential


class TestLMSVerifiableCredential(BaseTestUtils):
	def setUp(self):
		super().setUp()
		self._old_conf = {
			"lms_vc_enabled": frappe.conf.get("lms_vc_enabled"),
			"lms_vc_issuer_name": frappe.conf.get("lms_vc_issuer_name"),
			"lms_vc_public_base_url": frappe.conf.get("lms_vc_public_base_url"),
			"lms_vc_signing_secret": frappe.conf.get("lms_vc_signing_secret"),
		}
		self.instructor = self._create_user(
			f"instructor-{frappe.generate_hash()}@example.com",
			"Frappe",
			"Admin",
			["Moderator", "Course Creator"],
		)
		self.student = self._create_user(
			f"student-{frappe.generate_hash()}@example.com",
			"Student",
			"Member",
			["LMS Student"],
		)
		self.course = self._create_course(
			f"VC Course {frappe.generate_hash()}",
			instructor=self.instructor.email,
		)
		self._create_enrollment(self.student.email, self.course.name)

	def tearDown(self):
		frappe.db.delete("LMS Verifiable Credential", {"course": self.course.name})
		for key, value in self._old_conf.items():
			if value is None and key in frappe.conf:
				del frappe.conf[key]
			else:
				frappe.conf[key] = value
		super().tearDown()

	def _enable_credentials(self):
		frappe.conf.lms_vc_enabled = 1
		frappe.conf.lms_vc_issuer_name = "Test Issuer"
		frappe.conf.lms_vc_public_base_url = "http://test.localhost"
		frappe.conf.lms_vc_signing_secret = "test-secret"

	def test_disabled_module_creates_no_credential(self):
		frappe.conf.lms_vc_enabled = 0
		certificate = self._create_certificate(self.course.name, self.student.email)

		self.assertFalse(
			frappe.db.exists("LMS Verifiable Credential", {"certificate": certificate.name})
		)

	def test_enabled_module_creates_one_valid_credential(self):
		self._enable_credentials()
		certificate = self._create_certificate(self.course.name, self.student.email)
		credential_name = frappe.db.get_value(
			"LMS Verifiable Credential",
			{"certificate": certificate.name},
			"name",
		)

		self.assertTrue(credential_name)
		self.assertEqual(issue_credential_for_certificate(certificate), credential_name)

		credential_id = frappe.db.get_value(
			"LMS Verifiable Credential",
			credential_name,
			"credential_id",
		)
		result = verify_credential(credential_id)
		self.assertEqual(result["status"], "Issued")
		self.assertEqual(result["certificate"], certificate.name)

	def test_tampered_credential_is_invalid(self):
		self._enable_credentials()
		certificate = self._create_certificate(self.course.name, self.student.email)
		credential = frappe.get_doc("LMS Verifiable Credential", {"certificate": certificate.name})
		payload = json.loads(credential.credential_json)
		payload["credentialSubject"]["name"] = "Changed Name"
		credential.credential_json = frappe.as_json(payload)
		credential.save(ignore_permissions=True)

		result = verify_credential(credential.credential_id)
		self.assertEqual(result["status"], "Invalid")
