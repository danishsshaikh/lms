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
					{{ __('Turn Sunbird modules on for this LMS site.') }}
				</div>
			</div>

			<div class="space-y-4">
				<section class="max-w-5xl rounded-md border bg-surface-base">
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
									<Badge :theme="telemetryForm.enabled ? 'green' : 'gray'" :label="moduleStatus(telemetryForm.enabled)" />
								</div>
								<div class="mt-1 max-w-2xl text-sm leading-5 text-ink-gray-5">
									{{ __('Capture LMS activity as Sunbird-format learning events.') }}
								</div>
							</div>
						</div>

						<div class="flex items-center gap-3 rounded-md bg-surface-gray-1 px-3 py-2">
							<div>
								<div class="text-sm font-medium text-ink-gray-8">
									{{ __('Enable telemetry') }}
								</div>
								<div class="text-xs text-ink-gray-5">
									{{ __('Off means no event storage.') }}
								</div>
							</div>
							<Switch
								v-model="telemetryForm.enabled"
								:disabled="telemetrySave.loading"
								@change="saveTelemetrySettings"
							/>
						</div>
					</div>

					<div class="border-t">
						<button
							class="flex w-full items-center justify-between px-4 py-3 text-left text-sm font-medium text-ink-gray-8"
							@click="telemetryAdvancedOpen = !telemetryAdvancedOpen"
						>
							<span>{{ __('Advanced settings') }}</span>
							<span :class="[telemetryAdvancedOpen ? 'lucide-chevron-up' : 'lucide-chevron-down', 'size-4']" />
						</button>

						<div v-if="telemetryAdvancedOpen" class="grid grid-cols-1 gap-4 border-t p-4 lg:grid-cols-3">
							<div class="lg:col-span-2">
								<FormControl
									v-model="telemetryForm.base_url"
									:label="__('Optional Obsrv Receiver URL')"
									:placeholder="receiverPlaceholder"
								/>
								<div class="mt-1 text-xs leading-4 text-ink-gray-5">
									{{ __('Only needed when exporting stored telemetry events outside LMS.') }}
								</div>
							</div>
							<FormControl v-model="telemetryForm.dataset_id" :label="__('Dataset ID')" />
							<div class="lg:col-span-2">
								<FormControl
									v-model="telemetryForm.identity_salt"
									type="password"
									:label="__('Identity Salt')"
									:placeholder="identitySaltPlaceholder"
								/>
								<div class="mt-1 flex flex-wrap items-center gap-2 text-xs leading-4 text-ink-gray-5">
									<span>{{ __('Secret used to pseudonymize users in telemetry payloads.') }}</span>
									<button class="font-medium text-ink-gray-8 underline" @click="generateTelemetrySalt">
										{{ __('Generate local salt') }}
									</button>
								</div>
							</div>
							<FormControl
								v-model="telemetryForm.auth_token"
								type="password"
								:label="__('Auth Token')"
								:placeholder="authTokenPlaceholder"
							/>
							<FormControl
								v-model="telemetryForm.batch_size"
								type="number"
								:label="__('Batch Size')"
							/>
							<FormControl
								v-model="telemetryForm.timeout_seconds"
								type="number"
								:label="__('Timeout Seconds')"
							/>
						</div>
					</div>

					<div class="flex flex-wrap justify-end gap-2 border-t px-4 py-3">
						<Button :loading="telemetrySave.loading" @click="saveTelemetrySettings">
							{{ __('Save') }}
						</Button>
						<Button :loading="testEvent.loading" @click="sendTestEvent">
							{{ __('Send Test Event') }}
						</Button>
						<Button v-if="telemetryForm.enabled" @click="openTelemetry">
							{{ __('Open Sunbird Telemetry') }}
						</Button>
						<Button v-if="telemetryForm.base_url" :loading="flush.loading" @click="flushNow">
							{{ __('Export Events') }}
						</Button>
					</div>
				</section>

				<section class="max-w-5xl rounded-md border bg-surface-base">
					<div class="flex flex-col gap-4 p-4 md:flex-row md:items-start md:justify-between">
						<div class="flex gap-3">
							<div
								class="flex size-10 shrink-0 items-center justify-center rounded-md bg-surface-gray-2 text-ink-gray-8"
							>
								<span class="lucide-badge-check size-5" />
							</div>
							<div>
								<div class="flex flex-wrap items-center gap-2">
									<div class="text-base font-semibold text-ink-gray-9">
										{{ __('Sunbird RC Certificates') }}
									</div>
									<Badge :theme="vcForm.enabled ? 'green' : 'gray'" :label="moduleStatus(vcForm.enabled)" />
								</div>
								<div class="mt-1 max-w-2xl text-sm leading-5 text-ink-gray-5">
									{{ __('Issue local Sunbird RC compatible verifiable credentials and QR verification links for LMS certificates.') }}
								</div>
							</div>
						</div>

						<div class="flex items-center gap-3 rounded-md bg-surface-gray-1 px-3 py-2">
							<div>
								<div class="text-sm font-medium text-ink-gray-8">
									{{ __('Enable certificates') }}
								</div>
								<div class="text-xs text-ink-gray-5">
									{{ __('Off means normal LMS certificates only.') }}
								</div>
							</div>
							<Switch
								v-model="vcForm.enabled"
								:disabled="vcSave.loading"
								@change="saveVcSettings"
							/>
						</div>
					</div>

					<div class="grid grid-cols-1 gap-4 border-t p-4 lg:grid-cols-2">
						<FormControl v-model="vcForm.issuer_name" :label="__('Issuer Name')" />
						<FormControl
							v-model="vcForm.public_base_url"
							:label="__('Public Base URL')"
							:placeholder="publicBaseUrlPlaceholder"
						/>
						<div class="lg:col-span-2">
							<FormControl
								v-model="vcForm.signing_secret"
								type="password"
								:label="__('Signing Secret')"
								:placeholder="signingSecretPlaceholder"
							/>
							<div class="mt-1 flex flex-wrap items-center gap-2 text-xs leading-4 text-ink-gray-5">
								<span>{{ __('Secret used to sign local verifiable credentials.') }}</span>
								<button class="font-medium text-ink-gray-8 underline" @click="generateSigningSecret">
									{{ __('Generate signing secret') }}
								</button>
							</div>
						</div>
					</div>

					<div class="border-t">
						<button
							class="flex w-full items-center justify-between px-4 py-3 text-left text-sm font-medium text-ink-gray-8"
							@click="vcAdvancedOpen = !vcAdvancedOpen"
						>
							<span>{{ __('Advanced external Sunbird RC settings') }}</span>
							<span :class="[vcAdvancedOpen ? 'lucide-chevron-up' : 'lucide-chevron-down', 'size-4']" />
						</button>

						<div v-if="vcAdvancedOpen" class="grid grid-cols-1 gap-4 border-t p-4 lg:grid-cols-3">
							<div class="flex items-center gap-3 rounded-md bg-surface-gray-1 px-3 py-2">
								<div>
									<div class="text-sm font-medium text-ink-gray-8">
										{{ __('External issuer') }}
									</div>
									<div class="text-xs text-ink-gray-5">
										{{ __('Staged for future RC issuer calls.') }}
									</div>
								</div>
								<Switch v-model="vcForm.external_enabled" :disabled="vcSave.loading" />
							</div>
							<FormControl v-model="vcForm.external_base_url" :label="__('External RC Base URL')" />
							<FormControl
								v-model="vcForm.external_auth_token"
								type="password"
								:label="__('External Auth Token')"
								:placeholder="externalTokenPlaceholder"
							/>
							<FormControl
								v-model="vcForm.timeout_seconds"
								type="number"
								:label="__('Timeout Seconds')"
							/>
						</div>
					</div>

					<div class="flex flex-wrap justify-end gap-2 border-t px-4 py-3">
						<Button :loading="vcSave.loading" @click="saveVcSettings">
							{{ __('Save') }}
						</Button>
						<Button v-if="vcForm.enabled" @click="openCertificates">
							{{ __('Open Sunbird RC Certificates') }}
						</Button>
					</div>
				</section>
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
const telemetryAdvancedOpen = ref(false)
const vcAdvancedOpen = ref(false)
const lastTelemetryForm = ref({})
const lastVcForm = ref({})

const telemetryForm = reactive({
	enabled: 0,
	base_url: '',
	dataset_id: 'frappe_lms_learning_events',
	identity_salt: '',
	auth_token: '',
	batch_size: 100,
	timeout_seconds: 5,
})

const vcForm = reactive({
	enabled: 0,
	issuer_name: 'Frappe Learning',
	public_base_url: '',
	signing_secret: '',
	external_enabled: 0,
	external_base_url: '',
	external_auth_token: '',
	timeout_seconds: 5,
})

const receiverPlaceholder = computed(() => {
	const host = window.location.hostname || 'localhost'
	return `http://${host}:3000`
})

const publicBaseUrlPlaceholder = computed(() => window.location.origin)

const telemetrySettings = createResource({
	url: 'lms.lms.telemetry.get_telemetry_settings',
	auto: true,
	onSuccess(data) {
		if (telemetrySave.loading) return
		applyTelemetrySettings(data)
	},
})

const vcSettings = createResource({
	url: 'lms.lms.verifiable_credentials.get_vc_settings',
	auto: true,
	onSuccess(data) {
		if (vcSave.loading) return
		applyVcSettings(data)
	},
})

const telemetrySave = createResource({
	url: 'lms.lms.telemetry.update_telemetry_settings',
	makeParams() {
		ensureTelemetrySaltForEnable()
		return {
			settings: {
				enabled: telemetryForm.enabled ? 1 : 0,
				base_url: telemetryForm.base_url,
				dataset_id: telemetryForm.dataset_id,
				identity_salt: telemetryForm.identity_salt,
				auth_token: telemetryForm.auth_token,
				batch_size: telemetryForm.batch_size,
				timeout_seconds: telemetryForm.timeout_seconds,
			},
		}
	},
	onSuccess(data) {
		applyTelemetrySettings(data)
		setTelemetrySidebarEnabled(data.enabled)
		toast.success(__('Sunbird telemetry settings saved'))
	},
	onError(error) {
		restoreTelemetryForm()
		toast.error(error.messages?.[0] || error)
	},
})

const vcSave = createResource({
	url: 'lms.lms.verifiable_credentials.update_vc_settings',
	makeParams() {
		ensureSigningSecretForEnable()
		return {
			settings: {
				enabled: vcForm.enabled ? 1 : 0,
				issuer_name: vcForm.issuer_name,
				public_base_url: vcForm.public_base_url || window.location.origin,
				signing_secret: vcForm.signing_secret,
				external_enabled: vcForm.external_enabled ? 1 : 0,
				external_base_url: vcForm.external_base_url,
				external_auth_token: vcForm.external_auth_token,
				timeout_seconds: vcForm.timeout_seconds,
			},
		}
	},
	onSuccess(data) {
		applyVcSettings(data)
		setVcSidebarEnabled(data.enabled)
		toast.success(__('Sunbird RC certificate settings saved'))
	},
	onError(error) {
		restoreVcForm()
		toast.error(error.messages?.[0] || error)
	},
})

const testEvent = createResource({
	url: 'lms.lms.telemetry.send_telemetry_test_event',
	onSuccess(data) {
		if (!data?.ok) {
			toast.error(data?.reason || __('Test event was not stored'))
			telemetrySettings.reload()
			return
		}
		toast.success(__('Test event stored'))
		telemetrySettings.reload()
	},
	onError(error) {
		toast.error(error.messages?.[0] || error)
		telemetrySettings.reload()
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
		telemetrySettings.reload()
	},
	onError(error) {
		toast.error(error.messages?.[0] || error)
		telemetrySettings.reload()
	},
})

const moduleStatus = (enabled) => (enabled ? __('Enabled') : __('Disabled'))

const identitySaltPlaceholder = computed(() => {
	return telemetrySettings.data?.identity_salt_configured
		? __('Configured, leave blank to keep')
		: __('Generated automatically when enabled')
})

const authTokenPlaceholder = computed(() => {
	return telemetrySettings.data?.auth_token_configured ? __('Configured, leave blank to keep') : __('Optional')
})

const signingSecretPlaceholder = computed(() => {
	return vcSettings.data?.signing_secret_configured
		? __('Configured, leave blank to keep')
		: __('Generated automatically when enabled')
})

const externalTokenPlaceholder = computed(() => {
	return vcSettings.data?.external_auth_token_configured ? __('Configured, leave blank to keep') : __('Optional')
})

const snapshotTelemetryForm = () => ({
	enabled: telemetryForm.enabled ? 1 : 0,
	base_url: telemetryForm.base_url,
	dataset_id: telemetryForm.dataset_id,
	identity_salt: telemetryForm.identity_salt,
	auth_token: telemetryForm.auth_token,
	batch_size: telemetryForm.batch_size,
	timeout_seconds: telemetryForm.timeout_seconds,
})

const snapshotVcForm = () => ({
	enabled: vcForm.enabled ? 1 : 0,
	issuer_name: vcForm.issuer_name,
	public_base_url: vcForm.public_base_url,
	signing_secret: vcForm.signing_secret,
	external_enabled: vcForm.external_enabled ? 1 : 0,
	external_base_url: vcForm.external_base_url,
	external_auth_token: vcForm.external_auth_token,
	timeout_seconds: vcForm.timeout_seconds,
})

const applyTelemetrySettings = (data = {}) => {
	if (telemetrySettings.data) Object.assign(telemetrySettings.data, data)
	telemetryForm.enabled = data.enabled ? 1 : 0
	telemetryForm.base_url = data.base_url || ''
	telemetryForm.dataset_id = data.dataset_id || 'frappe_lms_learning_events'
	telemetryForm.identity_salt = ''
	telemetryForm.auth_token = ''
	telemetryForm.batch_size = data.batch_size || 100
	telemetryForm.timeout_seconds = data.timeout_seconds || 5
	lastTelemetryForm.value = snapshotTelemetryForm()
}

const applyVcSettings = (data = {}) => {
	if (vcSettings.data) Object.assign(vcSettings.data, data)
	vcForm.enabled = data.enabled ? 1 : 0
	vcForm.issuer_name = data.issuer_name || 'Frappe Learning'
	vcForm.public_base_url = data.public_base_url || window.location.origin
	vcForm.signing_secret = ''
	vcForm.external_enabled = data.external_enabled ? 1 : 0
	vcForm.external_base_url = data.external_base_url || ''
	vcForm.external_auth_token = ''
	vcForm.timeout_seconds = data.timeout_seconds || 5
	lastVcForm.value = snapshotVcForm()
}

const restoreTelemetryForm = () => Object.assign(telemetryForm, lastTelemetryForm.value)
const restoreVcForm = () => Object.assign(vcForm, lastVcForm.value)

const setTelemetrySidebarEnabled = (enabled) => {
	if (userResource.data) userResource.data.is_sunbird_telemetry_enabled = !!enabled
	window.dispatchEvent(new CustomEvent('lms:sunbird-telemetry-toggle', { detail: { enabled: !!enabled } }))
}

const setVcSidebarEnabled = (enabled) => {
	if (userResource.data) userResource.data.is_sunbird_vc_enabled = !!enabled
	window.dispatchEvent(new CustomEvent('lms:sunbird-vc-toggle', { detail: { enabled: !!enabled } }))
}

const generateLocalSecret = () => {
	if (window.crypto?.getRandomValues) {
		const bytes = new Uint8Array(24)
		window.crypto.getRandomValues(bytes)
		return Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('')
	}
	return `${Date.now()}-${Math.random().toString(36).slice(2)}-${Math.random().toString(36).slice(2)}`
}

const generateTelemetrySalt = () => {
	telemetryForm.identity_salt = generateLocalSecret()
	toast.success(__('Local identity salt generated'))
}

const generateSigningSecret = () => {
	vcForm.signing_secret = generateLocalSecret()
	toast.success(__('Signing secret generated'))
}

const ensureTelemetrySaltForEnable = () => {
	if (
		telemetryForm.enabled &&
		!telemetrySettings.data?.identity_salt_configured &&
		!telemetryForm.identity_salt
	) {
		telemetryForm.identity_salt = generateLocalSecret()
	}
}

const ensureSigningSecretForEnable = () => {
	if (
		vcForm.enabled &&
		!vcSettings.data?.signing_secret_configured &&
		!vcForm.signing_secret
	) {
		vcForm.signing_secret = generateLocalSecret()
	}
}

const saveTelemetrySettings = () => {
	if (telemetrySave.loading) return
	telemetrySave.submit()
}

const saveVcSettings = () => {
	if (vcSave.loading) return
	vcSave.submit()
}

const sendTestEvent = () => testEvent.submit()
const flushNow = () => flush.submit()
const openTelemetry = () => router.push({ name: 'SunbirdTelemetry' })
const openCertificates = () => router.push({ name: 'SunbirdCertificates' })

usePageMeta(() => {
	return {
		title: __('Integrations'),
		icon: brand.favicon,
	}
})
</script>
