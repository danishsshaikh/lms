import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
	call: vi.fn(() => Promise.resolve({ ok: true })),
	interact: vi.fn(),
	initialize: vi.fn(),
}))

vi.mock('frappe-ui', () => ({
	call: mocks.call,
}))

vi.mock('@project-sunbird/telemetry-sdk', () => ({
	$t: {
		initialize: mocks.initialize,
		interact: mocks.interact,
	},
}))

describe('telemetry utils', () => {
	beforeEach(() => {
		mocks.call.mockClear()
		mocks.interact.mockClear()
		mocks.initialize.mockClear()
		vi.resetModules()
	})

	it('builds route context from route patterns instead of raw full paths', async () => {
		const { getRouteTelemetryContext } = await import('@/utils/telemetry')
		const context = getRouteTelemetryContext({
			name: 'Profile',
			path: '/user/jane',
			fullPath: '/user/jane?secret=value',
			params: { username: 'jane', courseName: 'course-1' },
			matched: [{ path: '/user/:username' }],
		} as any)

		expect(context.route_name).toBe('Profile')
		expect(context.route_pattern).toBe('/user/:username')
		expect(context.course).toBe('course-1')
		expect(JSON.stringify(context)).not.toContain('jane')
		expect(JSON.stringify(context)).not.toContain('secret')
	})

	it('strips client-side PII before calling the backend', async () => {
		const { trackClientEvent } = await import('@/utils/telemetry')
		trackClientEvent({
			event_type: 'search_performed',
			context: {
				query: 'private query',
				email: 'student@example.com',
				query_hash: 'abc123',
				query_length: 13,
			},
			object_type: 'Search',
			object_id: 'lms_search',
		})

		expect(mocks.call).toHaveBeenCalledWith(
			'lms.lms.telemetry.track_client_event',
			expect.objectContaining({
				event_type: 'search_performed',
				context: {
					query_hash: 'abc123',
					query_length: 13,
				},
			})
		)
		expect(JSON.stringify(mocks.call.mock.calls[0][1])).not.toContain('private query')
		expect(JSON.stringify(mocks.call.mock.calls[0][1])).not.toContain('student@example.com')
	})
})
