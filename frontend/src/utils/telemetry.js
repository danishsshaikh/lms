import { call } from 'frappe-ui'
import { $t } from '@project-sunbird/telemetry-sdk'

let initialized = false
let capturedEvent = null

const stableParamKeys = [
	'courseName',
	'chapterNumber',
	'lessonNumber',
	'quizID',
	'assignmentID',
	'batchName',
	'programName',
	'certificateID',
]

const initSunbirdTelemetry = () => {
	if (initialized) return
	try {
		$t.initialize({
			pdata: { id: 'frappe_lms', ver: '1.0', pid: 'lms' },
			env: 'lms',
			channel: window.location.hostname,
			uid: 'anonymous',
			batchsize: 1,
			enableValidation: false,
			dispatcher: {
				dispatch(event) {
					capturedEvent = event
				},
			},
		})
		initialized = true
	} catch (error) {
		console.warn('[Telemetry] Sunbird SDK initialization failed', error)
	}
}

const fallbackEvent = (event_type, context, object_type, object_id) => ({
	id: 'frappe.lms.telemetry',
	ver: '3.0',
	eid: event_type.toUpperCase(),
	ets: Date.now(),
	mid: window.crypto?.randomUUID
		? window.crypto.randomUUID()
		: `${Date.now()}-${Math.random()}`,
	context,
	object: {
		id: object_id || event_type,
		type: object_type || event_type,
	},
	edata: {
		type: event_type,
	},
})

const safeContext = (context = {}) => {
	const next = { ...context }
	delete next.query
	delete next.search_query
	delete next.answer
	delete next.answers
	delete next.file_name
	delete next.filename
	delete next.file_url
	delete next.attachment
	delete next.assignment_attachment
	delete next.email
	delete next.full_name
	delete next.username
	delete next.user
	return next
}

export const hashString = async (value) => {
	const text = String(value || '')
	if (!window.crypto?.subtle) return ''
	const bytes = new TextEncoder().encode(text)
	const digest = await window.crypto.subtle.digest('SHA-256', bytes)
	return Array.from(new Uint8Array(digest))
		.map((byte) => byte.toString(16).padStart(2, '0'))
		.join('')
}

export const getRouteTelemetryContext = (route) => {
	const params = {}
	stableParamKeys.forEach((key) => {
		if (route.params?.[key]) params[key] = route.params[key]
	})

	return safeContext({
		route_name: route.name,
		route_pattern: route.matched?.[route.matched.length - 1]?.path || route.path,
		...params,
		course: route.params?.courseName,
		source_page: route.name,
	})
}

export const trackClientEvent = ({
	event_type,
	context = {},
	object_type,
	object_id,
	course,
	lesson,
} = {}) => {
	if (!event_type) return
	const cleanContext = safeContext(context)
	initSunbirdTelemetry()
	capturedEvent = null

	try {
		$t.interact({
			type: 'OTHER',
			id: event_type,
			pageid: cleanContext.route_name || cleanContext.source_page || 'lms',
			subtype: event_type,
			objid: object_id,
		})
	} catch (error) {
		console.warn('[Telemetry] Sunbird event generation failed', error)
	}

	call('lms.lms.telemetry.track_client_event', {
		event_type,
		context: cleanContext,
		object_type,
		object_id,
		event: capturedEvent || fallbackEvent(event_type, cleanContext, object_type, object_id),
		course: course || cleanContext.course || cleanContext.courseName,
		lesson: lesson || cleanContext.lesson,
	}).catch((error) => {
		console.warn('[Telemetry] Client event was not recorded', error)
	})
}
