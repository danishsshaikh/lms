import hashlib
import hmac
import json
import os
import uuid
from datetime import datetime
from typing import Any

import frappe
import requests
from frappe import _
from frappe.utils import add_to_date, cint, get_datetime, now_datetime


DOCTYPE = "LMS Telemetry Event"
DEFAULT_DATASET_ID = "frappe_lms_learning_events"
LOGGER_NAME = "lms.telemetry"

SUPPORTED_EVENT_TYPES = {
	"route_viewed",
	"course_viewed",
	"lesson_viewed",
	"lesson_content_viewed",
	"video_started",
	"video_paused",
	"video_resumed",
	"video_seeked",
	"video_progress",
	"video_completed",
	"quiz_started",
	"quiz_question_viewed",
	"quiz_answer_changed",
	"assignment_viewed",
	"assignment_file_selected",
	"discussion_viewed",
	"discussion_reply_started",
	"search_performed",
	"profile_viewed",
	"certificate_viewed",
	"telemetry_logs_viewed",
	"course_enrolled",
	"course_unenrolled",
	"lesson_completed",
	"quiz_submitted",
	"quiz_passed",
	"quiz_failed",
	"assignment_submitted",
	"assignment_graded",
	"certificate_issued",
	"batch_enrolled",
	"program_enrolled",
	"payment_completed",
	"live_class_created",
	"live_class_joined",
	"course_created",
	"course_published",
	"course_updated",
	"lesson_created",
	"lesson_updated",
}

PII_KEYS = {
	"answer",
	"answers",
	"assignment_attachment",
	"attachment",
	"bio",
	"content",
	"description",
	"email",
	"file",
	"file_name",
	"file_url",
	"filename",
	"first_name",
	"for_user",
	"from_user",
	"full_name",
	"headline",
	"instructor",
	"last_name",
	"member",
	"member_name",
	"member_username",
	"mobile",
	"name_of_user",
	"phone",
	"profile",
	"profile_text",
	"query",
	"raw_answer",
	"reply",
	"search_query",
	"owner",
	"evaluator",
	"text",
	"user",
	"user_id",
	"user_name",
	"username",
}


def _logger():
	return frappe.logger(LOGGER_NAME)


def is_enabled() -> bool:
	return bool(cint(frappe.conf.get("lms_obsrv_enabled", 0)))


def _get_config():
	return frappe._dict(
		enabled=is_enabled(),
		base_url=(frappe.conf.get("lms_obsrv_base_url") or "").rstrip("/"),
		dataset_id=frappe.conf.get("lms_obsrv_dataset_id") or DEFAULT_DATASET_ID,
		identity_salt=frappe.conf.get("lms_obsrv_identity_salt"),
		auth_token=frappe.conf.get("lms_obsrv_auth_token"),
		batch_size=cint(frappe.conf.get("lms_obsrv_batch_size") or 100) or 100,
		timeout_seconds=cint(frappe.conf.get("lms_obsrv_timeout_seconds") or 5) or 5,
	)


def _only_system_manager():
	if "System Manager" not in frappe.get_roles():
		frappe.throw(_("Only System Managers can configure telemetry."), frappe.PermissionError)


def _load_site_config():
	path = frappe.get_site_path("site_config.json")
	if not os.path.exists(path):
		return path, {}
	with open(path) as site_config_file:
		return path, json.load(site_config_file)


def _write_site_config(updates: dict):
	path, site_config = _load_site_config()
	site_config.update(updates)
	with open(path, "w") as site_config_file:
		json.dump(site_config, site_config_file, indent=1, sort_keys=True)
		site_config_file.write("\n")
	for key, value in updates.items():
		frappe.conf[key] = value


def _can_record(config=None) -> bool:
	config = config or _get_config()
	return _get_recording_blocker(config) is None


def _get_recording_blocker(config=None):
	config = config or _get_config()
	if not config.enabled:
		return _("Sunbird telemetry is disabled.")
	if not config.identity_salt:
		return _("Identity salt is required before telemetry events can be stored.")
	if not frappe.db.exists("DocType", DOCTYPE):
		return _("LMS Telemetry Event is missing. Run bench migrate before recording telemetry.")
	return None


def _get_telemetry_status(config=None):
	config = config or _get_config()
	blocker = _get_recording_blocker(config)
	status = frappe._dict(
		enabled=config.enabled,
		recording_ready=not blocker,
		recording_blocker=blocker,
		base_url_configured=bool(config.base_url),
		identity_salt_configured=bool(config.identity_salt),
		pending_count=0,
		failed_count=0,
		last_event_at=None,
		last_error=None,
	)

	if not frappe.db.exists("DocType", DOCTYPE):
		return status

	status.pending_count = frappe.db.count(DOCTYPE, {"status": "Pending"})
	status.failed_count = frappe.db.count(DOCTYPE, {"status": "Failed"})
	last_event = frappe.get_all(
		DOCTYPE,
		fields=["creation", "last_error"],
		order_by="creation desc",
		limit_page_length=1,
	)
	if last_event:
		status.last_event_at = last_event[0].creation
		status.last_error = last_event[0].last_error

	return status


def get_pseudonymous_actor_id(user: str) -> str | None:
	if not user or user == "Guest":
		return None

	salt = frappe.conf.get("lms_obsrv_identity_salt")
	if not salt:
		return None

	return hmac.new(str(salt).encode(), str(user).encode(), hashlib.sha256).hexdigest()


def _parse_json(value: Any, fallback=None):
	if value is None:
		return fallback
	if isinstance(value, (dict, list)):
		return value
	try:
		return json.loads(value)
	except Exception:
		return fallback


def _safe_scalar(value):
	if isinstance(value, (str, int, float, bool)) or value is None:
		return value
	if isinstance(value, datetime):
		return value.isoformat()
	return str(value)


def _strip_pii(value):
	if isinstance(value, dict):
		clean = {}
		for key, item in value.items():
			key_text = str(key)
			if key_text.lower() in PII_KEYS:
				continue
			clean[key_text] = _strip_pii(item)
		return clean
	if isinstance(value, list):
		return [_strip_pii(item) for item in value]
	return _safe_scalar(value)


def _build_event(
	event_type: str,
	actor_user: str,
	context: dict | None = None,
	object_type: str | None = None,
	object_id: str | None = None,
	metadata: dict | None = None,
	client_event: dict | None = None,
) -> tuple[str, dict]:
	event_id = str(
		(client_event or {}).get("mid")
		or (client_event or {}).get("id")
		or (client_event or {}).get("event_id")
		or uuid.uuid4()
	)
	ts = now_datetime().isoformat()
	actor_id = get_pseudonymous_actor_id(actor_user)

	event = _strip_pii(client_event or {})
	if not isinstance(event, dict):
		event = {}

	event.update(
		{
			"id": event.get("id") or "frappe.lms.telemetry",
			"ver": event.get("ver") or "3.0",
			"eid": event.get("eid") or event_type.upper(),
			"ets": event.get("ets") or int(now_datetime().timestamp() * 1000),
			"mid": event_id,
			"actor": {"id": actor_id, "type": "User"},
			"context": {
				"pdata": {"id": "frappe_lms", "ver": getattr(frappe, "__version__", "unknown"), "pid": "lms"},
				"env": "lms",
				"channel": frappe.local.site,
				"cdata": [],
				**_strip_pii(context or {}),
			},
			"object": {
				"id": _safe_scalar(object_id) if object_id else event_id,
				"type": _safe_scalar(object_type) if object_type else event_type,
			},
			"edata": {
				"type": event_type,
				"metadata": _strip_pii(metadata or {}),
			},
			"syncts": ts,
		}
	)

	return event_id, event


def record_event(
	event_type: str,
	member: str | None = None,
	course: str | None = None,
	lesson: str | None = None,
	object_type: str | None = None,
	object_id: str | None = None,
	context: dict | None = None,
	metadata: dict | None = None,
	client_event: dict | None = None,
	actor_user: str | None = None,
	raise_on_error: bool = False,
):
	try:
		config = _get_config()
		blocker = _get_recording_blocker(config)
		if blocker:
			_logger().warning(blocker)
			if raise_on_error:
				frappe.throw(blocker)
			return None

		if event_type not in SUPPORTED_EVENT_TYPES:
			message = _("Unsupported Sunbird telemetry event ignored: {0}").format(event_type)
			_logger().warning(message)
			if raise_on_error:
				frappe.throw(message)
			return None

		actor_user = actor_user or member or frappe.session.user
		if not actor_user or actor_user == "Guest":
			if raise_on_error:
				frappe.throw(_("A logged-in user is required to record telemetry."))
			return None

		event_id, payload = _build_event(
			event_type=event_type,
			actor_user=actor_user,
			context=context,
			object_type=object_type,
			object_id=object_id,
			metadata=metadata,
			client_event=client_event,
		)

		doc = frappe.get_doc(
			{
				"doctype": DOCTYPE,
				"event_id": event_id,
				"event_type": event_type,
				"status": "Pending",
				"attempt_count": 0,
				"payload": frappe.as_json(payload),
				"member": member or actor_user,
				"course": course,
				"lesson": lesson,
				"object_type": object_type,
				"object_id": object_id,
			}
		)
		doc.insert(ignore_permissions=True)
		return doc.name
	except frappe.UniqueValidationError:
		if raise_on_error:
			frappe.throw(_("This telemetry event has already been recorded."))
		return None
	except frappe.ValidationError:
		raise
	except Exception:
		frappe.log_error(title="Sunbird telemetry record failed", message=frappe.get_traceback())
		if raise_on_error:
			frappe.throw(_("Telemetry event could not be stored. Check Error Log for details."))
		return None


@frappe.whitelist()
def track_client_event(
	event_type: str,
	context: str | dict | None = None,
	object_type: str | None = None,
	object_id: str | None = None,
	event: str | dict | None = None,
	course: str | None = None,
	lesson: str | None = None,
):
	if frappe.session.user == "Guest":
		frappe.throw(_("You must be logged in to record telemetry."), frappe.PermissionError)

	event_name = record_event(
		event_type=event_type,
		member=frappe.session.user,
		course=course,
		lesson=lesson,
		object_type=object_type,
		object_id=object_id,
		context=_parse_json(context, {}),
		metadata=_parse_json(context, {}),
		client_event=_parse_json(event, {}),
		actor_user=frappe.session.user,
	)
	return {"ok": True, "recorded": bool(event_name), "event": event_name}


@frappe.whitelist()
def get_telemetry_settings():
	if not _has_log_access():
		frappe.throw(_("You do not have permission to view telemetry settings."), frappe.PermissionError)

	config = _get_config()
	status = _get_telemetry_status(config)
	return {
		"enabled": config.enabled,
		"base_url": config.base_url,
		"dataset_id": config.dataset_id,
		"identity_salt_configured": bool(config.identity_salt),
		"auth_token_configured": bool(config.auth_token),
		"batch_size": config.batch_size,
		"timeout_seconds": config.timeout_seconds,
		"can_configure": "System Manager" in frappe.get_roles(),
		"recording_ready": status.recording_ready,
		"recording_blocker": status.recording_blocker,
		"base_url_configured": status.base_url_configured,
		"pending_count": status.pending_count,
		"failed_count": status.failed_count,
		"last_event_at": status.last_event_at,
		"last_error": status.last_error,
	}


@frappe.whitelist()
def get_telemetry_status():
	if not _has_log_access():
		frappe.throw(_("You do not have permission to view telemetry status."), frappe.PermissionError)

	return dict(_get_telemetry_status())


@frappe.whitelist()
def update_telemetry_settings(settings: str | dict):
	_only_system_manager()
	settings = _parse_json(settings, {}) or {}

	updates = {
		"lms_obsrv_enabled": 1 if cint(settings.get("enabled")) else 0,
		"lms_obsrv_base_url": (settings.get("base_url") or "").strip().rstrip("/"),
		"lms_obsrv_dataset_id": (settings.get("dataset_id") or DEFAULT_DATASET_ID).strip(),
		"lms_obsrv_batch_size": max(cint(settings.get("batch_size") or 100), 1),
		"lms_obsrv_timeout_seconds": max(cint(settings.get("timeout_seconds") or 5), 1),
	}

	if "identity_salt" in settings and settings.get("identity_salt"):
		updates["lms_obsrv_identity_salt"] = settings.get("identity_salt")
	if "auth_token" in settings and settings.get("auth_token"):
		updates["lms_obsrv_auth_token"] = settings.get("auth_token")

	if updates["lms_obsrv_enabled"] and not (
		updates.get("lms_obsrv_identity_salt") or frappe.conf.get("lms_obsrv_identity_salt")
	):
		frappe.throw(_("Identity salt is required when telemetry is enabled."))

	_write_site_config(updates)
	return get_telemetry_settings()


@frappe.whitelist()
def send_telemetry_test_event():
	_only_system_manager()
	status = _get_telemetry_status()
	if not status.recording_ready:
		return {
			"ok": False,
			"reason": status.recording_blocker or _("Telemetry is not ready to record events."),
			"status": dict(status),
		}

	name = record_event(
		"telemetry_logs_viewed",
		member=frappe.session.user,
		object_type="Telemetry Test",
		object_id="frontend_configuration",
		metadata={"source_page": "TelemetryLogs", "test_event": True},
		actor_user=frappe.session.user,
		raise_on_error=True,
	)
	if not name:
		return {
			"ok": False,
			"reason": _("Telemetry event could not be stored. Check telemetry status and Error Log."),
			"status": dict(status),
		}
	return {"ok": True, "event": name, "status": dict(_get_telemetry_status())}


@frappe.whitelist()
def flush_pending_events_now():
	_only_system_manager()
	return flush_pending_events()


def _next_retry(attempt_count: int):
	delay_seconds = min(5 * (2 ** max(attempt_count - 1, 0)), 3600)
	return add_to_date(now_datetime(), seconds=delay_seconds)


def _get_due_events(limit: int):
	pending = frappe.get_all(
		DOCTYPE,
		filters={"status": "Pending"},
		fields=["name", "payload", "attempt_count"],
		order_by="creation asc",
		limit_page_length=limit,
	)
	if len(pending) >= limit:
		return pending

	failed = frappe.get_all(
		DOCTYPE,
		filters={
			"status": "Failed",
			"next_retry_at": ["<=", now_datetime()],
		},
		fields=["name", "payload", "attempt_count"],
		order_by="next_retry_at asc, creation asc",
		limit_page_length=limit - len(pending),
	)
	return pending + failed


def flush_pending_events(limit: int | None = None):
	config = _get_config()
	if not config.enabled:
		return {"sent": 0, "skipped": "disabled"}
	if not config.base_url:
		_logger().warning("Sunbird telemetry enabled without lms_obsrv_base_url; skipping flush.")
		return {"sent": 0, "skipped": "missing_base_url"}

	batch_size = limit or config.batch_size
	rows = _get_due_events(batch_size)
	if not rows:
		return {"sent": 0}

	msgid = str(uuid.uuid4())
	events = [_parse_json(row.payload, {}) for row in rows]
	envelope = {
		"id": "frappe.lms.telemetry",
		"ver": "1.0",
		"ts": now_datetime().isoformat(),
		"params": {"msgid": msgid},
		"data": {"events": events},
	}
	headers = {"Content-Type": "application/json"}
	if config.auth_token:
		headers["Authorization"] = f"Bearer {config.auth_token}"

	try:
		response = requests.post(
			f"{config.base_url}/v2/data/in/{config.dataset_id}",
			json=envelope,
			headers=headers,
			timeout=config.timeout_seconds,
		)
		response.raise_for_status()
	except Exception as exc:
		error = str(exc)[:1000]
		for row in rows:
			attempt_count = cint(row.attempt_count) + 1
			frappe.db.set_value(
				DOCTYPE,
				row.name,
				{
					"status": "Failed",
					"attempt_count": attempt_count,
					"next_retry_at": _next_retry(attempt_count),
					"last_error": error,
				},
				update_modified=False,
			)
		return {"sent": 0, "failed": len(rows)}

	sent_at = now_datetime()
	for row in rows:
		frappe.db.set_value(
			DOCTYPE,
			row.name,
			{
				"status": "Sent",
				"obsrv_msgid": msgid,
				"sent_at": sent_at,
				"last_error": None,
			},
			update_modified=False,
		)
	return {"sent": len(rows), "msgid": msgid}


def _has_log_access(user: str | None = None):
	roles = set(frappe.get_roles(user))
	return bool(roles & {"System Manager", "Moderator", "Course Creator"})


def _get_instructor_courses(user: str):
	return frappe.get_all(
		"Course Instructor",
		filters={"instructor": user, "parenttype": "LMS Course"},
		pluck="parent",
	)


@frappe.whitelist()
def get_telemetry_log_data(
	event_type: str | None = None,
	status: str | None = None,
	course: str | None = None,
	limit: int | str = 100,
):
	user = frappe.session.user
	if not _has_log_access(user):
		frappe.throw(_("You do not have permission to view telemetry logs."), frappe.PermissionError)

	filters = {}
	if event_type:
		filters["event_type"] = event_type
	if status:
		filters["status"] = status
	if course:
		filters["course"] = course

	roles = set(frappe.get_roles(user))
	if "System Manager" not in roles and "Moderator" not in roles:
		courses = _get_instructor_courses(user)
		if course and course not in courses:
			frappe.throw(_("You do not have permission to view telemetry logs for this course."), frappe.PermissionError)
		filters["course"] = ["in", courses or ["__none"]]

	limit = min(cint(limit) or 100, 500)
	rows = frappe.get_all(
		DOCTYPE,
		filters=filters,
		fields=[
			"name",
			"creation",
			"event_type",
			"status",
			"member",
			"course",
			"lesson",
			"object_type",
			"object_id",
			"payload",
			"last_error",
		],
		order_by="creation desc",
		limit_page_length=limit,
	)

	summary_filters = dict(filters)
	summary_filters.pop("status", None)
	status_counts = {
		"Pending": frappe.db.count(DOCTYPE, {**summary_filters, "status": "Pending"}),
		"Sent": frappe.db.count(DOCTYPE, {**summary_filters, "status": "Sent"}),
		"Failed": frappe.db.count(DOCTYPE, {**summary_filters, "status": "Failed"}),
	}
	event_type_counts = []
	for supported_event_type in sorted(SUPPORTED_EVENT_TYPES):
		count = frappe.db.count(DOCTYPE, {**summary_filters, "event_type": supported_event_type})
		if count:
			event_type_counts.append(frappe._dict(event_type=supported_event_type, count=count))
	event_type_counts = sorted(event_type_counts, key=lambda row: row.count, reverse=True)[:25]

	for row in rows:
		payload = _parse_json(row.payload, {})
		row.metadata = (payload.get("edata") or {}).get("metadata") or {}
		row.payload = None

	return {
		"summary": {
			"total": sum(status_counts.values()),
			"sent": status_counts.get("Sent", 0),
			"pending": status_counts.get("Pending", 0),
			"failed": status_counts.get("Failed", 0),
			"event_types": event_type_counts,
		},
		"rows": rows,
		"event_types": sorted(SUPPORTED_EVENT_TYPES),
		"statuses": ["Pending", "Sent", "Failed"],
	}
