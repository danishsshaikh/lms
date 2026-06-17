import frappe


def execute():
	if not frappe.db.table_exists("LMS Telemetry Event"):
		return

	try:
		frappe.db.add_unique("LMS Telemetry Event", ["event_id"])
	except Exception:
		frappe.log_error(
			title="Telemetry event unique index creation failed",
			message=frappe.get_traceback(),
		)

	for field in ("status", "next_retry_at", "event_type"):
		try:
			frappe.db.add_index("LMS Telemetry Event", [field])
		except Exception:
			frappe.log_error(
				title=f"Telemetry event {field} index creation failed",
				message=frappe.get_traceback(),
			)
