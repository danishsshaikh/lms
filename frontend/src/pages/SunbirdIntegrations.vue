<template>
	<div class="flex h-full flex-col">
		<header
			class="sticky top-0 z-10 flex items-center justify-between border-b bg-surface-base px-3 py-2.5 sm:px-5"
		>
			<Breadcrumbs class="h-7" :items="[{ label: __('Integrations') }]" />
		</header>

		<div class="flex-1 overflow-auto p-5">
			<div class="mb-5 max-w-3xl">
				<div class="text-xl font-semibold text-ink-gray-9">
					{{ __('Integrations') }}
				</div>
				<div class="mt-1 text-sm leading-5 text-ink-gray-5">
					{{ __('Turn Sunbird modules on for this LMS site. Telemetry events are captured locally and shown in the Sunbird Telemetry dashboard.') }}
				</div>
			</div>

			<div class="max-w-5xl rounded-md border bg-surface-base">
				<div class="flex flex-col gap-4 p-4 md:flex-row md:items-start md:justify-between">
					<div class="flex gap-3">
						<div
							class="flex size-10 shrink-0 items-center justify-center rounded-md bg-surface-gray-2 text-ink-gray-8"
						>
							<span class="lucide-activity size-5" />
						</div>
						<div>
							<div class="flex flex-wrap items-center gap-2">
								<div class="text-base font-semibold text-ink-gray-9">
									{{ __('Sunbird Telemetry') }}
								</div>
								<Badge :theme="settingsForm.enabled ? 'green' : 'gray'" :label="statusLabel" />
							</div>
							<div class="mt-1 max-w-2xl text-sm leading-5 text-ink-gray-5">
								{{ __('Capture learning events from LMS activity and show them in the Sunbird Telemetry dashboard.') }}
							</div>
						</div>
					</div>

					<div class="flex items-center gap-3 rounded-md bg-surface-gray-1 px-3 py-2">
						<div>
							<div class="text-sm font-medium text-ink-gray-8">
								{{ __('Enable telemetry') }}
							</div>
							<div class="text-xs text-ink-gray-5">
								{{ __('Off means no storage and no sending.') }}
							</div>
						</div>
						<Switch
							v-model="settingsForm.enabled"
							:disabled="settingsSave.loading"
							@change="saveSettings"
						/>
					</div>
				</div>

				<div class="border-t">
					<button
						class="flex w-full items-center justify-between px-4 py-3 text-left text-sm font-medium text-ink-gray-8"
						@click="advancedOpen = !advancedOpen"
					>
						<span>{{ __('Advanced settings') }}</span>
						<span :class="[advancedOpen ? 'lucide-chevron-up' : 'lucide-chevron-down', 'size-4']" />
					</button>

					<div v-if="advancedOpen" class="grid grid-cols-1 gap-4 border-t p-4 lg:grid-cols-3">
						<div class="lg:col-span-2">
							<FormControl
								v-model="settingsForm.base_url"
								:label="__('Optional Obsrv Receiver URL')"
								:placeholder="receiverPlaceholder"
							/>
							<div class="mt-1 text-xs leading-4 text-ink-gray-5">
								{{ __('Only needed if you want to export stored events to a mock or external receiver. Leave blank for dashboard-only telemetry.') }}
							</div>
						</div>
						<div>
							<FormControl v-model="settingsForm.dataset_id" :label="__('Dataset ID')" />
							<div class="mt-1 text-xs leading-4 text-ink-gray-5">
								{{ __('Only used for optional external export.') }}
							</div>
						</div>
						<div class="lg:col-span-2">
							<FormControl
								v-model="settingsForm.identity_salt"
								type="password"
								:label="__('Identity Salt')"
								:placeholder="identitySaltPlaceholder"
							/>
							<div class="mt-1 flex flex-wrap items-center gap-2 text-xs leading-4 text-ink-gray-5">
								<span>{{ __('Secret used to pseudonymize users before storing telemetry payloads.') }}</span>
								<button class="font-medium text-ink-gray-8 underline" @click="generateSalt">
									{{ __('Generate local salt') }}
								</button>
							</div>
						</div>
						<div>
							<FormControl
								v-model="settingsForm.auth_token"
								type="password"
								:label="__('Auth Token')"
								:placeholder="authTokenPlaceholder"
							/>
							<div class="mt-1 text-xs leading-4 text-ink-gray-5">
								{{ __('Only needed if the optional receiver requires one.') }}
							</div>
						</div>
						<FormControl
							v-model="settingsForm.batch_size"
							type="number"
							:label="__('Batch Size')"
						/>
						<FormControl
							v-model="settingsForm.timeout_seconds"
							type="number"
							:label="__('Timeout Seconds')"
						/>
					</div>
				</div>

				<div class="flex flex-wrap justify-end gap-2 border-t px-4 py-3">
					<Button :loading="settingsSave.loading" @click="saveSettings">
						{{ __('Save') }}
					</Button>
					<Button :loading="testEvent.loading" @click="sendTestEvent">
						{{ __('Send Test Event') }}
					</Button>
					<Button v-if="settingsForm.enabled" @click="openTelemetry">
						{{ __('Open Sunbird Telemetry') }}
					</Button>
					<Button v-if="settingsForm.base_url" :loading="flush.loading" @click="flushNow">
						{{ __('Export Events') }}
					</Button>
				</div>
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
import { computed, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { sessionStore } from '@/stores/session'
import { usersStore } from '@/stores/user'
import Switch from '@/components/Controls/Switch.vue'

const { brand } = sessionStore()
const { userResource } = usersStore()
const router = useRouter()
const advancedOpen = ref(false)
const lastSavedForm = ref({})
const settingsForm = reactive({
	enabled: 0,
	base_url: '',
	dataset_id: 'frappe_lms_learning_events',
	identity_salt: '',
	auth_token: '',
	batch_size: 100,
	timeout_seconds: 5,
})

const receiverPlaceholder = computed(() => {
	const host = window.location.hostname || 'localhost'
	return `http://${host}:3000`
})

const settings = createResource({
	url: 'lms.lms.telemetry.get_telemetry_settings',
	auto: true,
	onSuccess(data) {
		if (settingsSave.loading) return
		applySettingsData(data)
	},
})

const settingsSave = createResource({
	url: 'lms.lms.telemetry.update_telemetry_settings',
	makeParams() {
		ensureSaltForEnable()
		return {
			settings: {
				enabled: settingsForm.enabled ? 1 : 0,
				base_url: settingsForm.base_url,
				dataset_id: settingsForm.dataset_id,
				identity_salt: settingsForm.identity_salt,
				auth_token: settingsForm.auth_token,
				batch_size: settingsForm.batch_size,
				timeout_seconds: settingsForm.timeout_seconds,
			},
		}
	},
	onSuccess(data) {
		applySettingsData(data)
		setTelemetrySidebarEnabled(data.enabled)
		toast.success(__('Sunbird telemetry settings saved'))
	},
	onError(error) {
		restoreLastSavedForm()
		toast.error(error.messages?.[0] || error)
	},
})

const testEvent = createResource({
	url: 'lms.lms.telemetry.send_telemetry_test_event',
	onSuccess(data) {
		if (!data?.ok) {
			toast.error(data?.reason || __('Test event was not stored'))
			settings.reload()
			return
		}
		toast.success(__('Test event stored'))
		settings.reload()
	},
	onError(error) {
		toast.error(error.messages?.[0] || error)
		settings.reload()
	},
})

const flush = createResource({
	url: 'lms.lms.telemetry.flush_pending_events_now',
	onSuccess(data) {
		if (data.skipped === 'missing_base_url') {
			toast.warning(__('No optional receiver is configured. Events still remain visible in Sunbird Telemetry.'))
		} else if (data.skipped === 'disabled') {
			toast.warning(__('Telemetry is disabled. Nothing was exported.'))
		} else if (data.failed) {
			toast.error(__('Export failed for {0} event(s). Local events are still visible.').format(data.failed))
		} else {
			toast.success(__('Export complete: {0} sent').format(data.sent || 0))
		}
		settings.reload()
	},
	onError(error) {
		toast.error(error.messages?.[0] || error)
		settings.reload()
	},
})

const statusLabel = computed(() => {
	return settingsForm.enabled ? __('Enabled') : __('Disabled')
})

const identitySaltPlaceholder = computed(() => {
	return settings.data?.identity_salt_configured
		? __('Configured, leave blank to keep')
		: __('Generated automatically when enabled')
})

const authTokenPlaceholder = computed(() => {
	return settings.data?.auth_token_configured ? __('Configured, leave blank to keep') : __('Optional')
})

const snapshotForm = () => ({
	enabled: settingsForm.enabled ? 1 : 0,
	base_url: settingsForm.base_url,
	dataset_id: settingsForm.dataset_id,
	identity_salt: settingsForm.identity_salt,
	auth_token: settingsForm.auth_token,
	batch_size: settingsForm.batch_size,
	timeout_seconds: settingsForm.timeout_seconds,
})

const applySettingsData = (data = {}) => {
	if (settings.data) {
		Object.assign(settings.data, data)
	}
	settingsForm.enabled = data.enabled ? 1 : 0
	settingsForm.base_url = data.base_url || ''
	settingsForm.dataset_id = data.dataset_id || 'frappe_lms_learning_events'
	settingsForm.identity_salt = ''
	settingsForm.auth_token = ''
	settingsForm.batch_size = data.batch_size || 100
	settingsForm.timeout_seconds = data.timeout_seconds || 5
	lastSavedForm.value = snapshotForm()
}

const restoreLastSavedForm = () => {
	Object.assign(settingsForm, lastSavedForm.value)
}

const setTelemetrySidebarEnabled = (enabled) => {
	if (userResource.data) {
		userResource.data.is_sunbird_telemetry_enabled = !!enabled
	}
	window.dispatchEvent(
		new CustomEvent('lms:sunbird-telemetry-toggle', {
			detail: { enabled: !!enabled },
		})
	)
}

const generateLocalSalt = () => {
	if (window.crypto?.getRandomValues) {
		const bytes = new Uint8Array(24)
		window.crypto.getRandomValues(bytes)
		return Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('')
	}
	return `${Date.now()}-${Math.random().toString(36).slice(2)}-${Math.random().toString(36).slice(2)}`
}

const generateSalt = () => {
	settingsForm.identity_salt = generateLocalSalt()
	toast.success(__('Local identity salt generated'))
}

const ensureSaltForEnable = () => {
	if (
		settingsForm.enabled &&
		!settings.data?.identity_salt_configured &&
		!settingsForm.identity_salt
	) {
		settingsForm.identity_salt = generateLocalSalt()
	}
}

const saveSettings = () => {
	if (settingsSave.loading) return
	settingsSave.submit()
}

const sendTestEvent = () => {
	testEvent.submit()
}

const flushNow = () => {
	flush.submit()
}

const openTelemetry = () => {
	router.push({ name: 'SunbirdTelemetry' })
}

usePageMeta(() => {
	return {
		title: __('Integrations'),
		icon: brand.favicon,
	}
})
</script>
