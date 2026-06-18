import hashlib
import hmac
import io
import json
import os
import uuid
from copy import deepcopy
from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, get_url, getdate, now_datetime, today


DOCTYPE = "LMS Verifiable Credential"
DEFAULT_ISSUER_NAME = "Frappe Learning"
LOGGER_NAME = "lms.verifiable_credentials"


def _logger():
	return frappe.logger(LOGGER_NAME)


def is_enabled() -> bool:
	return bool(cint(frappe.conf.get("lms_vc_enabled", 0)))


def _get_config():
	public_base_url = (frappe.conf.get("lms_vc_public_base_url") or "").strip().rstrip("/")
	if not public_base_url:
		public_base_url = get_url().rstrip("/")

	return frappe._dict(
		enabled=is_enabled(),
		issuer_name=(frappe.conf.get("lms_vc_issuer_name") or DEFAULT_ISSUER_NAME).strip(),
		public_base_url=public_base_url,
		signing_secret=frappe.conf.get("lms_vc_signing_secret"),
		external_enabled=bool(cint(frappe.conf.get("lms_vc_external_enabled", 0))),
		external_base_url=(frappe.conf.get("lms_vc_external_base_url") or "").strip().rstrip("/"),
		external_auth_token=frappe.conf.get("lms_vc_external_auth_token"),
		timeout_seconds=cint(frappe.conf.get("lms_vc_timeout_seconds") or 5) or 5,
	)


def _only_system_manager():
	if "System Manager" not in frappe.get_roles():
		frappe.throw(_("Only System Managers can configure Sunbird RC Certificates."), frappe.PermissionError)


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


def _parse_json(value: Any, fallback=None):
	if value is None:
		return fallback
	if isinstance(value, (dict, list)):
		return value
	try:
		return json.loads(value)
	except Exception:
		return fallback


def _canonical_json(value: dict) -> str:
	return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _sign_payload(payload: dict, secret: str) -> str:
	return hmac.new(str(secret).encode(), _canonical_json(payload).encode(), hashlib.sha256).hexdigest()


def _credential_without_proof(credential: dict) -> dict:
	payload = deepcopy(credential)
	payload.pop("proof", None)
	return payload


def _get_signing_blocker(config=None):
	config = config or _get_config()
	if not config.enabled:
		return _("Sunbird RC Certificates are disabled.")
	if not config.signing_secret:
		return _("Signing secret is required before verifiable credentials can be issued.")
	if not frappe.db.exists("DocType", DOCTYPE):
		return _("LMS Verifiable Credential is missing. Run bench migrate before issuing credentials.")
	return None


def _make_credential_id() -> str:
	return f"urn:frappe-lms:credential:{uuid.uuid4()}"


def _verification_url(public_base_url: str, credential_id: str) -> str:
	return f"{public_base_url}/verify-certificate?credential_id={credential_id}"


def _get_certificate_doc(certificate):
	if hasattr(certificate, "doctype"):
		return certificate
	return frappe.get_doc("LMS Certificate", certificate)


def _get_certificate_values(certificate_doc):
	course_title = certificate_doc.course_title
	if certificate_doc.course and not course_title:
		course_title = frappe.db.get_value("LMS Course", certificate_doc.course, "title")

	batch_title = certificate_doc.batch_title
	if certificate_doc.batch_name and not batch_title:
		batch_title = frappe.db.get_value("LMS Batch", certificate_doc.batch_name, "title")

	member_name = certificate_doc.member_name
	if certificate_doc.member and not member_name:
		member_name = frappe.db.get_value("User", certificate_doc.member, "full_name")

	return frappe._dict(
		member=certificate_doc.member,
		member_name=member_name,
		course=certificate_doc.course,
		course_title=course_title,
		batch=certificate_doc.batch_name,
		batch_title=batch_title,
		issue_date=certificate_doc.issue_date,
		expiry_date=certificate_doc.expiry_date,
	)


def _generate_qr_svg(url: str) -> str:
	try:
		import segno
	except Exception:
		_logger().warning("segno is not installed; verifiable credential QR SVG was not generated.")
		return ""

	output = io.BytesIO()
	segno.make(url, error="m").save(output, kind="svg", xmldecl=False, svgns=True, scale=4)
	return output.getvalue().decode()


def _build_credential(certificate_doc, config=None):
	config = config or _get_config()
	values = _get_certificate_values(certificate_doc)
	issued_at = now_datetime()
	credential_id = _make_credential_id()
	verification_url = _verification_url(config.public_base_url, credential_id)

	credential = {
		"@context": [
			"https://www.w3.org/2018/credentials/v1",
			"https://sunbird.org/credentials/v1",
		],
		"type": ["VerifiableCredential", "SunbirdRCCertificateCredential"],
		"id": credential_id,
		"issuer": {
			"id": config.public_base_url,
			"name": config.issuer_name,
			"type": "Organization",
		},
		"issuanceDate": issued_at.isoformat(),
		"credentialSubject": {
			"id": f"frappe-lms-user:{values.member}",
			"name": values.member_name,
			"certificate": {
				"id": certificate_doc.name,
				"issueDate": str(values.issue_date) if values.issue_date else None,
				"expiryDate": str(values.expiry_date) if values.expiry_date else None,
			},
			"course": {
				"id": values.course,
				"name": values.course_title,
			},
			"batch": {
				"id": values.batch,
				"name": values.batch_title,
			},
		},
		"credentialStatus": {
			"id": verification_url,
			"type": "FrappeLMSCredentialStatus",
		},
	}

	if values.expiry_date:
		credential["expirationDate"] = f"{values.expiry_date}T23:59:59"

	signature = _sign_payload(credential, config.signing_secret)
	credential["proof"] = {
		"type": "HmacSha256Proof",
		"created": issued_at.isoformat(),
		"proofPurpose": "assertionMethod",
		"verificationMethod": config.public_base_url,
		"jws": signature,
	}

	return frappe._dict(
		credential_id=credential_id,
		verification_url=verification_url,
		credential_json=credential,
		credential_hash=signature,
		qr_svg=_generate_qr_svg(verification_url),
		issued_at=issued_at,
		subject_values=values,
	)


def issue_credential_for_certificate(certificate, raise_on_error: bool = False):
	certificate_doc = None
	try:
		config = _get_config()
		blocker = _get_signing_blocker(config)
		if blocker:
			_logger().warning(blocker)
			if raise_on_error:
				frappe.throw(blocker)
			return None

		certificate_doc = _get_certificate_doc(certificate)
		existing = frappe.db.get_value(
			DOCTYPE,
			{"certificate": certificate_doc.name},
			["name", "status", "qr_svg", "credential_hash", "credential_json"],
			as_dict=True,
		)
		if existing:
			if existing.status == "Revoked":
				return existing.name
			if existing.status != "Failed" and _is_credential_complete(existing):
				return existing.name
			frappe.delete_doc(DOCTYPE, existing.name, force=True, ignore_permissions=True)

		built = _build_credential(certificate_doc, config)
		subject_values = built.subject_values
		doc = frappe.get_doc(
			{
				"doctype": DOCTYPE,
				"credential_id": built.credential_id,
				"certificate": certificate_doc.name,
				"status": "Issued",
				"issued_at": built.issued_at,
				"member": subject_values.member,
				"member_name": subject_values.member_name,
				"course": subject_values.course,
				"course_title": subject_values.course_title,
				"batch": subject_values.batch,
				"batch_title": subject_values.batch_title,
				"verification_url": built.verification_url,
				"credential_hash": built.credential_hash,
				"qr_svg": built.qr_svg,
				"credential_json": frappe.as_json(built.credential_json),
				"external_enabled": 1 if config.external_enabled else 0,
				"external_status": "Staged" if config.external_enabled else None,
			}
		)
		doc.insert(ignore_permissions=True)
		return doc.name
	except frappe.UniqueValidationError:
		return frappe.db.get_value(DOCTYPE, {"certificate": _get_certificate_doc(certificate).name}, "name")
	except Exception:
		if certificate_doc and frappe.db.exists("DocType", DOCTYPE):
			_record_failed_credential(certificate_doc, frappe.get_traceback())
		frappe.log_error(title="Sunbird RC credential creation failed", message=frappe.get_traceback())
		if raise_on_error:
			frappe.throw(_("Verifiable credential could not be created. Check Error Log for details."))
		return None


def _record_failed_credential(certificate_doc, error: str):
	if frappe.db.exists(DOCTYPE, {"certificate": certificate_doc.name}):
		return

	values = _get_certificate_values(certificate_doc)
	config = _get_config()
	credential_id = _make_credential_id()
	verification_url = _verification_url(config.public_base_url, credential_id)
	payload = {
		"id": credential_id,
		"type": ["VerifiableCredential", "SunbirdRCCertificateCredential"],
		"issuer": {"name": config.issuer_name},
		"credentialSubject": {"certificate": {"id": certificate_doc.name}},
		"error": (error or "")[:1000],
	}
	try:
		frappe.get_doc(
			{
				"doctype": DOCTYPE,
				"credential_id": credential_id,
				"certificate": certificate_doc.name,
				"status": "Failed",
				"issued_at": now_datetime(),
				"member": values.member,
				"member_name": values.member_name,
				"course": values.course,
				"course_title": values.course_title,
				"batch": values.batch,
				"batch_title": values.batch_title,
				"verification_url": verification_url,
				"credential_hash": "",
				"credential_json": frappe.as_json(payload),
				"external_error": (error or "")[:1000],
			}
		).insert(ignore_permissions=True)
	except Exception:
		frappe.log_error(
			title="Failed credential row creation failed",
			message=frappe.get_traceback(),
		)


def _is_credential_complete(row) -> bool:
	return bool(
		row
		and row.get("credential_hash")
		and row.get("credential_json")
		and row.get("qr_svg")
		and _verify_signature(row)
	)


def _effective_status(row):
	status = row.get("status") if isinstance(row, dict) else row.status
	if status == "Revoked":
		return "Revoked"
	if status == "Failed":
		return "Failed"

	certificate = row.get("certificate") if isinstance(row, dict) else row.certificate
	expiry_date = frappe.db.get_value("LMS Certificate", certificate, "expiry_date")
	if expiry_date and getdate(expiry_date) < getdate(today()):
		return "Expired"
	return status or "Issued"


def _verify_signature(row):
	credential = _parse_json(row.credential_json, {}) or {}
	proof = credential.get("proof") or {}
	expected = _sign_payload(_credential_without_proof(credential), frappe.conf.get("lms_vc_signing_secret") or "")
	return bool(
		expected
		and row.credential_hash
		and hmac.compare_digest(expected, row.credential_hash)
		and hmac.compare_digest(expected, proof.get("jws") or "")
	)


def verify_credential(credential_id: str | None):
	if not credential_id:
		return {"ok": False, "status": "Invalid", "reason": _("Missing credential ID.")}

	row = frappe.db.get_value(
		DOCTYPE,
		{"credential_id": credential_id},
		[
			"name",
			"credential_id",
			"certificate",
			"status",
			"issued_at",
			"member_name",
			"course",
			"course_title",
			"batch",
			"batch_title",
			"verification_url",
			"qr_svg",
			"credential_hash",
			"credential_json",
			"revoked_at",
			"revoke_reason",
		],
		as_dict=True,
	)
	if not row:
		return {"ok": False, "status": "Invalid", "reason": _("Credential was not found.")}

	certificate = frappe.db.get_value(
		"LMS Certificate",
		row.certificate,
		["name", "issue_date", "expiry_date", "published"],
		as_dict=True,
	)
	if not certificate:
		return {"ok": False, "status": "Invalid", "reason": _("Linked certificate was not found.")}

	signature_valid = _verify_signature(row)
	status = _effective_status(row)
	if not signature_valid:
		status = "Invalid"

	config = _get_config()
	return {
		"ok": signature_valid and status not in {"Invalid", "Failed"},
		"status": status,
		"reason": None if signature_valid else _("Credential signature does not match stored data."),
		"credential_id": row.credential_id,
		"certificate": row.certificate,
		"member_name": row.member_name,
		"course": row.course,
		"course_title": row.course_title,
		"batch": row.batch,
		"batch_title": row.batch_title,
		"issue_date": certificate.issue_date,
		"expiry_date": certificate.expiry_date,
		"issuer": config.issuer_name,
		"verification_url": row.verification_url,
		"qr_svg": row.qr_svg,
		"revoked_at": row.revoked_at,
		"revoke_reason": row.revoke_reason,
	}


@frappe.whitelist(allow_guest=True)
def verify_credential_public(credential_id: str | None = None):
	return verify_credential(credential_id)


def _has_dashboard_access(user: str | None = None):
	roles = set(frappe.get_roles(user))
	return bool(roles & {"System Manager", "Moderator", "Course Creator", "Batch Evaluator"})


def _get_user_courses(user: str):
	return frappe.get_all(
		"Course Instructor",
		filters={"instructor": user, "parenttype": "LMS Course"},
		pluck="parent",
	)


def _get_user_batches(user: str):
	return frappe.get_all(
		"Course Instructor",
		filters={"instructor": user, "parenttype": "LMS Batch"},
		pluck="parent",
	)


def _apply_dashboard_permissions(filters: dict, user: str):
	roles = set(frappe.get_roles(user))
	if "System Manager" in roles or "Moderator" in roles:
		return filters

	courses = _get_user_courses(user)
	batches = _get_user_batches(user)
	if filters.get("course") and filters.get("course") not in courses:
		frappe.throw(_("You do not have permission to view credentials for this course."), frappe.PermissionError)
	if filters.get("batch") and filters.get("batch") not in batches:
		frappe.throw(_("You do not have permission to view credentials for this batch."), frappe.PermissionError)

	if filters.get("course") or filters.get("batch"):
		return filters
	if courses:
		filters["course"] = ["in", courses]
	elif batches:
		filters["batch"] = ["in", batches]
	else:
		filters["name"] = "__no_access__"
	return filters


def _get_vc_status(config=None):
	config = config or _get_config()
	status = frappe._dict(
		enabled=config.enabled,
		issuing_ready=not _get_signing_blocker(config),
		issuing_blocker=_get_signing_blocker(config),
		public_base_url_configured=bool(frappe.conf.get("lms_vc_public_base_url")),
		signing_secret_configured=bool(config.signing_secret),
		external_enabled=config.external_enabled,
		last_credential_at=None,
		last_error=None,
	)
	if not frappe.db.exists("DocType", DOCTYPE):
		return status

	last = frappe.get_all(
		DOCTYPE,
		fields=["creation", "external_error"],
		order_by="creation desc",
		limit_page_length=1,
	)
	if last:
		status.last_credential_at = last[0].creation
		status.last_error = last[0].external_error
	return status


@frappe.whitelist()
def get_vc_settings():
	if not _has_dashboard_access(frappe.session.user):
		frappe.throw(_("You do not have permission to view Sunbird RC certificate settings."), frappe.PermissionError)

	config = _get_config()
	status = _get_vc_status(config)
	return {
		"enabled": config.enabled,
		"issuer_name": config.issuer_name,
		"public_base_url": config.public_base_url,
		"signing_secret_configured": bool(config.signing_secret),
		"external_enabled": config.external_enabled,
		"external_base_url": config.external_base_url,
		"external_auth_token_configured": bool(config.external_auth_token),
		"timeout_seconds": config.timeout_seconds,
		"can_configure": "System Manager" in frappe.get_roles(),
		"issuing_ready": status.issuing_ready,
		"issuing_blocker": status.issuing_blocker,
		"last_credential_at": status.last_credential_at,
		"last_error": status.last_error,
	}


@frappe.whitelist()
def update_vc_settings(settings: str | dict):
	_only_system_manager()
	settings = _parse_json(settings, {}) or {}

	enabled = 1 if cint(settings.get("enabled")) else 0
	updates = {
		"lms_vc_enabled": enabled,
		"lms_vc_issuer_name": (settings.get("issuer_name") or DEFAULT_ISSUER_NAME).strip(),
		"lms_vc_public_base_url": (settings.get("public_base_url") or get_url()).strip().rstrip("/"),
		"lms_vc_external_enabled": 1 if cint(settings.get("external_enabled")) else 0,
		"lms_vc_external_base_url": (settings.get("external_base_url") or "").strip().rstrip("/"),
		"lms_vc_timeout_seconds": max(cint(settings.get("timeout_seconds") or 5), 1),
	}

	if settings.get("signing_secret"):
		updates["lms_vc_signing_secret"] = settings.get("signing_secret")
	elif enabled and not frappe.conf.get("lms_vc_signing_secret"):
		updates["lms_vc_signing_secret"] = frappe.generate_hash(length=32)

	if settings.get("external_auth_token"):
		updates["lms_vc_external_auth_token"] = settings.get("external_auth_token")

	_write_site_config(updates)
	return get_vc_settings()


@frappe.whitelist()
def get_vc_dashboard_data(
	status: str | None = None,
	course: str | None = None,
	batch: str | None = None,
	member: str | None = None,
	limit: int | str = 100,
):
	user = frappe.session.user
	if not _has_dashboard_access(user):
		frappe.throw(_("You do not have permission to view Sunbird RC certificates."), frappe.PermissionError)

	filters = {}
	if course:
		filters["course"] = course
	if batch:
		filters["batch"] = batch
	if member:
		filters["member"] = member
	if status and status != "Expired":
		filters["status"] = status
	filters = _apply_dashboard_permissions(filters, user)

	limit = min(cint(limit) or 100, 500)
	rows = frappe.get_all(
		DOCTYPE,
		filters=filters,
		fields=[
			"name",
			"creation",
			"credential_id",
			"certificate",
			"member",
			"member_name",
			"course",
			"course_title",
			"batch",
			"batch_title",
			"status",
			"issued_at",
			"revoked_at",
			"revoke_reason",
			"verification_url",
			"external_status",
			"external_error",
		],
		order_by="creation desc",
		limit_page_length=limit,
	)

	for row in rows:
		row.effective_status = _effective_status(row)

	if status:
		rows = [row for row in rows if row.effective_status == status]

	summary_filters = dict(filters)
	summary_filters.pop("status", None)
	all_rows = frappe.get_all(DOCTYPE, filters=summary_filters, fields=["name", "status", "certificate"])
	counts = {"issued": 0, "valid": 0, "revoked": 0, "expired": 0, "failed": 0}
	for row in all_rows:
		counts["issued"] += 1
		effective_status = _effective_status(row)
		if effective_status == "Issued":
			counts["valid"] += 1
		elif effective_status == "Revoked":
			counts["revoked"] += 1
		elif effective_status == "Expired":
			counts["expired"] += 1
		elif effective_status == "Failed":
			counts["failed"] += 1

	return {
		"summary": counts,
		"rows": rows,
		"statuses": ["Issued", "Revoked", "Expired", "Failed"],
		"settings": get_vc_settings(),
	}


@frappe.whitelist()
def revoke_credential(name: str, reason: str | None = None):
	if not _has_dashboard_access(frappe.session.user):
		frappe.throw(_("You do not have permission to revoke credentials."), frappe.PermissionError)

	doc = frappe.get_doc(DOCTYPE, name)
	_apply_dashboard_permissions({"course": doc.course, "batch": doc.batch}, frappe.session.user)
	if "System Manager" not in frappe.get_roles() and "Moderator" not in frappe.get_roles():
		frappe.throw(_("Only System Managers and Moderators can revoke credentials."), frappe.PermissionError)

	doc.status = "Revoked"
	doc.revoked_at = now_datetime()
	doc.revoke_reason = reason
	doc.save(ignore_permissions=True)
	return {"ok": True}


@frappe.whitelist()
def regenerate_credential(certificate: str):
	if not _has_dashboard_access(frappe.session.user):
		frappe.throw(_("You do not have permission to regenerate credentials."), frappe.PermissionError)

	certificate_doc = frappe.get_doc("LMS Certificate", certificate)
	_apply_dashboard_permissions(
		{"course": certificate_doc.course, "batch": certificate_doc.batch_name},
		frappe.session.user,
	)
	existing = frappe.db.get_value(
		DOCTYPE,
		{"certificate": certificate},
		["name", "status", "qr_svg", "credential_hash", "credential_json"],
		as_dict=True,
	)
	if existing:
		if existing.status == "Revoked":
			return {"ok": True, "credential": existing.name, "existing": True}
		if existing.status != "Failed" and _is_credential_complete(existing):
			return {"ok": True, "credential": existing.name, "existing": True}
		frappe.delete_doc(DOCTYPE, existing.name, force=True, ignore_permissions=True)

	name = issue_credential_for_certificate(certificate_doc, raise_on_error=True)
	return {"ok": bool(name), "credential": name, "existing": False}


def get_certificate_verification_context(certificate: str):
	if not frappe.db.exists("DocType", DOCTYPE):
		return {}

	row = frappe.db.get_value(
		DOCTYPE,
		{"certificate": certificate, "status": "Issued"},
		["credential_id", "verification_url", "qr_svg"],
		as_dict=True,
	)
	return row or {}
