import frappe

from lms.lms.verifiable_credentials import verify_credential


def get_context(context):
	context.no_cache = 1
	context.credential_id = frappe.form_dict.get("credential_id")
	context.result = verify_credential(context.credential_id)
	context.title = "Verify Certificate"
