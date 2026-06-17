<template>
	<div class="flex h-full flex-col">
		<header
			class="sticky top-0 z-10 flex flex-wrap items-center justify-between gap-2 border-b bg-surface-base px-3 py-2.5 sm:px-5"
		>
			<Breadcrumbs class="h-7" :items="[{ label: __('Sunbird Telemetry') }]" />
			<div class="flex flex-wrap gap-2">
				<Button
					v-if="settings.data?.can_configure"
					:loading="testEvent.loading"
					@click="sendTestEvent"
				>
					{{ __('Send Test Event') }}
				</Button>
				<Button
					v-if="settings.data?.can_configure"
					:loading="flush.loading"
					@click="flushNow"
				>
					{{ __('Export Events') }}
				</Button>
				<Button :loading="logs.loading || settings.loading" @click="refresh">
					<template #prefix>
						<span class="lucide-refresh-cw size-4" />
					</template>
					{{ __('Refresh') }}
				</Button>
			</div>
		</header>

		<div class="flex-1 overflow-auto p-5">
			<div :class="['mb-5 rounded-md border px-4 py-3', statusBannerClass]">
				<div class="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
					<div>
						<div class="font-medium">{{ statusTitle }}</div>
						<div class="mt-1 text-sm leading-5">{{ statusDescription }}</div>
					</div>
					<Button v-if="settings.data?.can_configure" @click="openIntegrations">
						{{ __('Open Integrations') }}
					</Button>
				</div>
			</div>

			<div class="grid grid-cols-2 gap-3 lg:grid-cols-5">
				<div
					v-for="card in summaryCards"
					:key="card.label"
					class="rounded-md border p-3"
				>
					<div class="text-sm text-ink-gray-5">{{ card.label }}</div>
					<div class="mt-1 text-2xl font-semibold text-ink-gray-9">
						{{ card.value }}
					</div>
				</div>
			</div>

			<div class="mt-5 grid grid-cols-1 gap-3 md:grid-cols-4">
				<FormControl
					v-model="filters.event_type"
					type="select"
					:label="__('Event Type')"
					:options="eventTypeOptions"
				/>
				<FormControl
					v-model="filters.status"
					type="select"
					:label="__('Status')"
					:options="statusOptions"
				/>
				<FormControl
					v-model="filters.course"
					:label="__('Course')"
					:placeholder="__('Course ID')"
				/>
				<FormControl
					v-model="filters.limit"
					type="number"
					:label="__('Limit')"
				/>
			</div>

			<div class="mt-5 overflow-hidden rounded-md border">
				<table class="min-w-full divide-y divide-outline-gray-2 text-sm">
					<thead class="bg-surface-gray-2 text-left text-ink-gray-6">
						<tr>
							<th class="px-3 py-2 font-medium">{{ __('Time') }}</th>
							<th class="px-3 py-2 font-medium">{{ __('Event') }}</th>
							<th class="px-3 py-2 font-medium">{{ __('Status') }}</th>
							<th class="px-3 py-2 font-medium">{{ __('Member') }}</th>
							<th class="px-3 py-2 font-medium">{{ __('Course') }}</th>
							<th class="px-3 py-2 font-medium">{{ __('Metadata') }}</th>
						</tr>
					</thead>
					<tbody class="divide-y divide-outline-gray-1 bg-surface-base">
						<template v-for="row in logs.data?.rows || []" :key="row.name">
							<tr class="cursor-pointer hover:bg-surface-gray-1" @click="toggleRow(row.name)">
								<td class="whitespace-nowrap px-3 py-2 text-ink-gray-7">
									{{ dayjs(row.creation).format('DD MMM YYYY HH:mm') }}
								</td>
								<td class="px-3 py-2 font-medium text-ink-gray-9">
									{{ row.event_type }}
								</td>
								<td class="px-3 py-2">
									<Badge :theme="statusTheme(row.status)" :label="row.status" />
								</td>
								<td class="px-3 py-2 text-ink-gray-7">{{ row.member || '-' }}</td>
								<td class="px-3 py-2 text-ink-gray-7">{{ row.course || '-' }}</td>
								<td class="max-w-md px-3 py-2 text-ink-gray-7">
									<code class="line-clamp-2 whitespace-pre-wrap break-words">
										{{ compactMetadata(row) }}
									</code>
								</td>
							</tr>
							<tr v-if="selectedRowName === row.name" class="bg-surface-gray-1">
								<td colspan="6" class="px-3 py-3">
									<div class="grid gap-3 lg:grid-cols-3">
										<div class="text-sm">
											<div class="font-medium text-ink-gray-8">{{ __('Object') }}</div>
											<div class="mt-1 text-ink-gray-6">
												{{ row.object_type || '-' }}: {{ row.object_id || '-' }}
											</div>
											<div v-if="row.lesson" class="mt-2">
												<div class="font-medium text-ink-gray-8">{{ __('Lesson') }}</div>
												<div class="mt-1 text-ink-gray-6">{{ row.lesson }}</div>
											</div>
											<div v-if="row.last_error" class="mt-2">
												<div class="font-medium text-ink-red-6">{{ __('Last Error') }}</div>
												<div class="mt-1 whitespace-pre-wrap break-words text-ink-red-6">
													{{ row.last_error }}
												</div>
											</div>
										</div>
										<div class="lg:col-span-2">
											<div class="mb-1 text-sm font-medium text-ink-gray-8">
												{{ __('Metadata') }}
											</div>
											<pre class="max-h-72 overflow-auto rounded-md bg-surface-base p-3 text-xs leading-5 text-ink-gray-8">{{ fullMetadata(row) }}</pre>
										</div>
									</div>
								</td>
							</tr>
						</template>
						<tr v-if="!logs.loading && !logs.data?.rows?.length">
							<td colspan="6" class="px-3 py-12 text-center">
								<div class="font-medium text-ink-gray-8">{{ emptyTitle }}</div>
								<div class="mx-auto mt-1 max-w-lg text-sm leading-5 text-ink-gray-5">
									{{ emptyDescription }}
								</div>
								<Button
									v-if="settings.data?.can_configure"
									class="mt-4"
									@click="openIntegrations"
								>
									{{ __('Open Integrations') }}
								</Button>
							</td>
						</tr>
					</tbody>
				</table>
			</div>
		</div>
	</div>
</template>

<script setup>
import {
	Badge,
	Breadcrumbs,
	Button,
	createResource,
	FormControl,
	toast,
	usePageMeta,
} from 'frappe-ui'
import { computed, inject, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { sessionStore } from '@/stores/session'
import { trackClientEvent } from '@/utils/telemetry'

const { brand } = sessionStore()
const dayjs = inject('$dayjs')
const router = useRouter()
const selectedRowName = ref('')
const filters = reactive({
	event_type: '',
	status: '',
	course: '',
	limit: 100,
})

const settings = createResource({
	url: 'lms.lms.telemetry.get_telemetry_settings',
	auto: true,
})

const logs = createResource({
	url: 'lms.lms.telemetry.get_telemetry_log_data',
	makeParams() {
		return {
			event_type: filters.event_type || null,
			status: filters.status || null,
			course: filters.course || null,
			limit: filters.limit || 100,
		}
	},
	auto: true,
})

const testEvent = createResource({
	url: 'lms.lms.telemetry.send_telemetry_test_event',
	onSuccess(data) {
		if (!data?.ok) {
			toast.error(data?.reason || __('Test event was not stored'))
			refresh()
			return
		}
		toast.success(__('Test event stored'))
		refresh()
	},
	onError(error) {
		toast.error(error.messages?.[0] || error)
		refresh()
	},
})

const flush = createResource({
	url: 'lms.lms.telemetry.flush_pending_events_now',
	onSuccess(data) {
		if (data.skipped === 'missing_base_url') {
			toast.warning(__('No optional receiver is configured. Events still remain visible here.'))
		} else if (data.skipped === 'disabled') {
			toast.warning(__('Telemetry is disabled. Nothing was exported.'))
		} else if (data.failed) {
			toast.error(__('Export failed for {0} event(s). Local events are still visible.').format(data.failed))
		} else {
			toast.success(__('Export complete: {0} sent').format(data.sent || 0))
		}
		refresh()
	},
	onError(error) {
		toast.error(error.messages?.[0] || error)
		refresh()
	},
})

onMounted(() => {
	trackClientEvent({
		event_type: 'telemetry_logs_viewed',
		context: { source_page: 'TelemetryLogs' },
		object_type: 'Telemetry Logs',
		object_id: 'telemetry_logs',
	})
})

watch(filters, () => refreshLogs())

const summaryCards = computed(() => {
	const summary = logs.data?.summary || {}
	return [
		{ label: __('Total'), value: summary.total || 0 },
		{ label: __('Sent'), value: summary.sent || 0 },
		{ label: __('Pending'), value: summary.pending || 0 },
		{ label: __('Failed'), value: summary.failed || 0 },
		{ label: __('Event Types'), value: summary.event_types?.length || 0 },
	]
})

const eventTypeOptions = computed(() => [
	{ label: __('All'), value: '' },
	...(logs.data?.event_types || []).map((eventType) => ({
		label: eventType,
		value: eventType,
	})),
])

const statusOptions = computed(() => [
	{ label: __('All'), value: '' },
	...(logs.data?.statuses || []).map((status) => ({
		label: status,
		value: status,
	})),
])

const statusTitle = computed(() => {
	if (!settings.data?.enabled) return __('Telemetry is disabled')
	if (settings.data?.recording_ready) return __('Recording is ready')
	return __('Telemetry needs attention')
})

const statusDescription = computed(() => {
	if (!settings.data?.enabled) {
		return __('Enable Sunbird Telemetry in Integrations before LMS actions can create events.')
	}
	if (!settings.data?.recording_ready) {
		return settings.data?.recording_blocker || __('Events cannot be stored yet.')
	}
	if (settings.data?.last_error) {
		return __('Recording is enabled. Failed exports do not block the local dashboard.')
	}
	return __('Events are being captured locally and shown here. No receiver is needed for this dashboard.')
})

const statusBannerClass = computed(() => {
	if (!settings.data?.enabled) return 'bg-surface-gray-1 text-ink-gray-7'
	if (settings.data?.recording_ready) return 'bg-surface-green-1 text-ink-green-6'
	return 'bg-surface-red-1 text-ink-red-6'
})

const emptyTitle = computed(() => {
	if (!settings.data?.enabled) return __('No events because telemetry is disabled')
	if (!settings.data?.recording_ready) return __('No events because telemetry is not ready')
	return __('No telemetry events found')
})

const emptyDescription = computed(() => {
	if (!settings.data?.enabled) {
		return __('Turn it on from Integrations, then send a test event or use the LMS to populate this table.')
	}
	if (!settings.data?.recording_ready) {
		return settings.data?.recording_blocker || __('Fix the telemetry settings, then try again.')
	}
	return __('Send a test event or perform course, lesson, quiz, assignment, and video actions to create learning events.')
})

const statusTheme = (status) => {
	if (status === 'Sent') return 'green'
	if (status === 'Failed') return 'red'
	return 'orange'
}

const compactMetadata = (row) => {
	const metadata = row.metadata || {}
	const text = JSON.stringify(metadata)
	return text === '{}' ? '-' : text
}

const fullMetadata = (row) => {
	const metadata = {
		event_type: row.event_type,
		status: row.status,
		member: row.member,
		course: row.course,
		lesson: row.lesson,
		object_type: row.object_type,
		object_id: row.object_id,
		metadata: row.metadata || {},
	}
	return JSON.stringify(metadata, null, 2)
}

const toggleRow = (name) => {
	selectedRowName.value = selectedRowName.value === name ? '' : name
}

const refreshLogs = () => {
	selectedRowName.value = ''
	logs.reload()
}

const refresh = () => {
	selectedRowName.value = ''
	settings.reload()
	logs.reload()
}

const sendTestEvent = () => {
	testEvent.submit()
}

const flushNow = () => {
	flush.submit()
}

const openIntegrations = () => {
	router.push({ name: 'Integrations' })
}

usePageMeta(() => {
	return {
		title: __('Sunbird Telemetry'),
		icon: brand.favicon,
	}
})
</script>
