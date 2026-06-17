from unittest.mock import patch

import frappe
from frappe.tests import UnitTestCase

from lms.lms.telemetry import (
	DOCTYPE,
	flush_pending_events,
	get_telemetry_settings,
	get_pseudonymous_actor_id,
	record_event,
	send_telemetry_test_event,
	track_client_event,
)


class TestLMSTelemetryEvent(UnitTestCase):
	def setUp(self):
		super().setUp()
		self.old_config = {
			"lms_obsrv_enabled": frappe.conf.get("lms_obsrv_enabled"),
			"lms_obsrv_identity_salt": frappe.conf.get("lms_obsrv_identity_salt"),
			"lms_obsrv_base_url": frappe.conf.get("lms_obsrv_base_url"),
		}
		self.old_user = frappe.session.user
		frappe.db.delete(DOCTYPE)

	def tearDown(self):
		frappe.db.delete(DOCTYPE)
		for key, value in self.old_config.items():
			if value is None:
				frappe.conf.pop(key, None)
			else:
				frappe.conf[key] = value
		frappe.set_user(self.old_user)
		super().tearDown()

	def enable(self):
		frappe.conf["lms_obsrv_enabled"] = 1
		frappe.conf["lms_obsrv_identity_salt"] = "test-local-salt"

	def test_disabled_telemetry_creates_no_rows(self):
		frappe.conf["lms_obsrv_enabled"] = 0
		record_event("route_viewed", member="student@example.com", object_type="Route", object_id="Home")
		self.assertEqual(frappe.db.count(DOCTYPE), 0)

	def test_missing_salt_skips_safely(self):
		frappe.conf["lms_obsrv_enabled"] = 1
		frappe.conf.pop("lms_obsrv_identity_salt", None)
		record_event("route_viewed", member="student@example.com", object_type="Route", object_id="Home")
		self.assertEqual(frappe.db.count(DOCTYPE), 0)

	def test_test_event_reports_disabled_without_row(self):
		frappe.set_user("Administrator")
		frappe.conf["lms_obsrv_enabled"] = 0
		response = send_telemetry_test_event()
		self.assertFalse(response["ok"])
		self.assertIn("disabled", response["reason"].lower())
		self.assertEqual(frappe.db.count(DOCTYPE), 0)

	def test_test_event_reports_missing_salt_without_row(self):
		frappe.set_user("Administrator")
		frappe.conf["lms_obsrv_enabled"] = 1
		frappe.conf.pop("lms_obsrv_identity_salt", None)
		response = send_telemetry_test_event()
		self.assertFalse(response["ok"])
		self.assertIn("salt", response["reason"].lower())
		self.assertEqual(frappe.db.count(DOCTYPE), 0)

	def test_test_event_creates_pending_row_without_base_url(self):
		frappe.set_user("Administrator")
		self.enable()
		frappe.conf.pop("lms_obsrv_base_url", None)
		response = send_telemetry_test_event()
		self.assertTrue(response["ok"])
		self.assertTrue(response["event"])
		self.assertEqual(frappe.db.get_value(DOCTYPE, response["event"], "status"), "Pending")

	def test_settings_reports_recording_status(self):
		frappe.set_user("Administrator")
		self.enable()
		frappe.conf.pop("lms_obsrv_base_url", None)
		settings = get_telemetry_settings()
		self.assertTrue(settings["recording_ready"])
		self.assertFalse(settings["base_url_configured"])

	def test_unknown_event_type_is_ignored(self):
		self.enable()
		record_event("unknown_event", member="student@example.com")
		self.assertEqual(frappe.db.count(DOCTYPE), 0)

	def test_actor_id_is_pseudonymous(self):
		self.enable()
		actor_id = get_pseudonymous_actor_id("student@example.com")
		self.assertIsNotNone(actor_id)
		self.assertNotIn("student@example.com", actor_id)
		self.assertEqual(actor_id, get_pseudonymous_actor_id("student@example.com"))

	def test_pii_fields_are_stripped(self):
		self.enable()
		record_event(
			"quiz_submitted",
			member="student@example.com",
			object_type="LMS Quiz",
			object_id="quiz-1",
			metadata={
				"score_percentage": 80,
				"answer": "raw answer",
				"email": "student@example.com",
				"query": "private search",
			},
		)
		payload = frappe.db.get_value(DOCTYPE, {"event_type": "quiz_submitted"}, "payload")
		self.assertIn("score_percentage", payload)
		self.assertNotIn("raw answer", payload)
		self.assertNotIn("student@example.com", payload)
		self.assertNotIn("private search", payload)

	def test_track_client_event_replaces_actor(self):
		self.enable()
		frappe.set_user("Administrator")
		track_client_event(
			"route_viewed",
			context={"route_name": "Home"},
			object_type="Route",
			object_id="Home",
			event={"actor": {"id": "raw@example.com", "type": "User"}},
		)
		payload = frappe.db.get_value(DOCTYPE, {"event_type": "route_viewed"}, "payload")
		self.assertNotIn("raw@example.com", payload)
		self.assertIn(get_pseudonymous_actor_id("Administrator"), payload)

	def test_flush_success_marks_sent(self):
		self.enable()
		frappe.conf["lms_obsrv_base_url"] = "http://localhost:3000"
		record_event("route_viewed", member="student@example.com", object_type="Route", object_id="Home")
		with patch("lms.lms.telemetry.requests.post") as post:
			post.return_value.raise_for_status.return_value = None
			flush_pending_events()
		self.assertEqual(frappe.db.get_value(DOCTYPE, {"event_type": "route_viewed"}, "status"), "Sent")

	def test_flush_failure_schedules_retry(self):
		self.enable()
		frappe.conf["lms_obsrv_base_url"] = "http://localhost:3000"
		record_event("route_viewed", member="student@example.com", object_type="Route", object_id="Home")
		with patch("lms.lms.telemetry.requests.post", side_effect=Exception("down")):
			flush_pending_events()
		row = frappe.db.get_value(
			DOCTYPE,
			{"event_type": "route_viewed"},
			["status", "attempt_count", "next_retry_at", "last_error"],
			as_dict=True,
		)
		self.assertEqual(row.status, "Failed")
		self.assertEqual(row.attempt_count, 1)
		self.assertTrue(row.next_retry_at)
		self.assertIn("down", row.last_error)
