import frappe


def execute():
	if not frappe.db.table_exists("LMS Verifiable Credential"):
		return

	for fields, title in (
		(["credential_id"], "credential id"),
		(["certificate"], "certificate"),
	):
		try:
			frappe.db.add_unique("LMS Verifiable Credential", fields)
		except Exception:
			frappe.log_error(
				title=f"Verifiable credential {title} unique index creation failed",
				message=frappe.get_traceback(),
			)

	for field in ("status", "course", "batch", "member"):
		try:
			frappe.db.add_index("LMS Verifiable Credential", [field])
		except Exception:
			frappe.log_error(
				title=f"Verifiable credential {field} index creation failed",
				message=frappe.get_traceback(),
			)
