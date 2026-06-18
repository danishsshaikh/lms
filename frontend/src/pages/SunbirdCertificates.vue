<template>
	<div class="flex h-full flex-col">
		<header
			class="sticky top-0 z-10 flex flex-wrap items-center justify-between gap-2 border-b bg-surface-base px-3 py-2.5 sm:px-5"
		>
			<Breadcrumbs class="h-7" :items="[{ label: __('Sunbird RC Certificates') }]" />
			<div class="flex flex-wrap gap-2">
				<Button v-if="settings.data?.can_configure" :loading="regenerate.loading" @click="regenerateFromPrompt">
					{{ __('Regenerate') }}
				</Button>
				<Button :loading="dashboard.loading || settings.loading" @click="refresh">
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
				<div v-for="card in summaryCards" :key="card.label" class="rounded-md border p-3">
					<div class="text-sm text-ink-gray-5">{{ card.label }}</div>
					<div class="mt-1 text-2xl font-semibold text-ink-gray-9">
						{{ card.value }}
					</div>
				</div>
			</div>

			<div class="mt-5 grid grid-cols-1 gap-3 md:grid-cols-5">
				<FormControl
					v-model="filters.status"
					type="select"
					:label="__('Status')"
					:options="statusOptions"
				/>
				<FormControl v-model="filters.course" :label="__('Course')" :placeholder="__('Course ID')" />
				<FormControl v-model="filters.batch" :label="__('Batch')" :placeholder="__('Batch ID')" />
				<FormControl v-model="filters.member" :label="__('Member')" :placeholder="__('User ID')" />
				<FormControl v-model="filters.limit" type="number" :label="__('Limit')" />
			</div>

			<div class="mt-5 overflow-hidden rounded-md border">
				<table class="min-w-full divide-y divide-outline-gray-2 text-sm">
					<thead class="bg-surface-gray-2 text-left text-ink-gray-6">
						<tr>
							<th class="px-3 py-2 font-medium">{{ __('Issued') }}</th>
							<th class="px-3 py-2 font-medium">{{ __('Certificate') }}</th>
							<th class="px-3 py-2 font-medium">{{ __('Member') }}</th>
							<th class="px-3 py-2 font-medium">{{ __('Course / Batch') }}</th>
							<th class="px-3 py-2 font-medium">{{ __('Status') }}</th>
							<th class="px-3 py-2 font-medium">{{ __('Verification') }}</th>
							<th class="px-3 py-2 font-medium">{{ __('Actions') }}</th>
						</tr>
					</thead>
					<tbody class="divide-y divide-outline-gray-1 bg-surface-base">
						<template v-for="row in dashboard.data?.rows || []" :key="row.name">
							<tr class="hover:bg-surface-gray-1">
								<td class="whitespace-nowrap px-3 py-2 text-ink-gray-7">
									{{ row.issued_at ? dayjs(row.issued_at).format('DD MMM YYYY HH:mm') : '-' }}
								</td>
								<td class="px-3 py-2 font-medium text-ink-gray-9">
									{{ row.certificate }}
								</td>
								<td class="px-3 py-2 text-ink-gray-7">
									<div>{{ row.member_name || '-' }}</div>
									<div class="text-xs text-ink-gray-5">{{ row.member || '' }}</div>
								</td>
								<td class="px-3 py-2 text-ink-gray-7">
									<div>{{ row.course_title || row.course || '-' }}</div>
									<div v-if="row.batch || row.batch_title" class="text-xs text-ink-gray-5">
										{{ row.batch_title || row.batch }}
									</div>
								</td>
								<td class="px-3 py-2">
									<Badge :theme="statusTheme(row.effective_status)" :label="row.effective_status" />
								</td>
								<td class="max-w-sm px-3 py-2 text-ink-gray-7">
									<code class="line-clamp-1 break-all">{{ row.verification_url }}</code>
								</td>
								<td class="px-3 py-2">
									<div class="flex flex-wrap gap-2">
										<Button size="sm" @click="copyLink(row)">
											{{ __('Copy') }}
										</Button>
										<Button size="sm" @click="openVerification(row)">
											{{ __('Open') }}
										</Button>
										<Button
											v-if="canRevoke(row)"
											size="sm"
											:loading="revoke.loading && selectedName === row.name"
											@click="revokeCredential(row)"
										>
											{{ __('Revoke') }}
										</Button>
									</div>
								</td>
							</tr>
						</template>
						<tr v-if="!dashboard.loading && !dashboard.data?.rows?.length">
							<td colspan="7" class="px-3 py-12 text-center">
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

const { brand } = sessionStore()
const dayjs = inject('$dayjs')
const router = useRouter()
const selectedName = ref('')
const filters = reactive({
	status: '',
	course: '',
	batch: '',
	member: '',
	limit: 100,
})

const settings = createResource({
	url: 'lms.lms.verifiable_credentials.get_vc_settings',
	auto: true,
})

const dashboard = createResource({
	url: 'lms.lms.verifiable_credentials.get_vc_dashboard_data',
	makeParams() {
		return {
			status: filters.status || null,
			course: filters.course || null,
			batch: filters.batch || null,
			member: filters.member || null,
			limit: filters.limit || 100,
		}
	},
	auto: true,
})

const revoke = createResource({
	url: 'lms.lms.verifiable_credentials.revoke_credential',
	makeParams(values) {
		return values
	},
	onSuccess() {
		toast.success(__('Credential revoked'))
		refresh()
	},
	onError(error) {
		toast.error(error.messages?.[0] || error)
	},
})

const regenerate = createResource({
	url: 'lms.lms.verifiable_credentials.regenerate_credential',
	makeParams(values) {
		return values
	},
	onSuccess(data) {
		toast.success(data?.existing ? __('Credential already exists') : __('Credential regenerated'))
		refresh()
	},
	onError(error) {
		toast.error(error.messages?.[0] || error)
	},
})

const summaryCards = computed(() => {
	const summary = dashboard.data?.summary || {}
	return [
		{ label: __('Issued'), value: summary.issued || 0 },
		{ label: __('Valid'), value: summary.valid || 0 },
		{ label: __('Revoked'), value: summary.revoked || 0 },
		{ label: __('Expired'), value: summary.expired || 0 },
		{ label: __('Failed'), value: summary.failed || 0 },
	]
})

const statusOptions = computed(() => [
	{ label: __('All'), value: '' },
	...((dashboard.data?.statuses || []).map((status) => ({ label: status, value: status }))),
])

const statusBannerClass = computed(() => {
	if (!settings.data?.enabled) return 'bg-surface-gray-1 text-ink-gray-7'
	if (!settings.data?.issuing_ready) return 'bg-surface-amber-1 text-ink-amber-8'
	if (settings.data?.last_error) return 'bg-surface-red-1 text-ink-red-7'
	return 'bg-surface-green-1 text-ink-green-7'
})

const statusTitle = computed(() => {
	if (!settings.data?.enabled) return __('Sunbird RC Certificates are disabled')
	if (!settings.data?.issuing_ready) return __('Sunbird RC Certificates need setup')
	if (settings.data?.last_error) return __('Last credential action had an error')
	return __('Sunbird RC Certificates are enabled')
})

const statusDescription = computed(() => {
	if (!settings.data?.enabled) {
		return __('Enable this integration to create QR verifiable credentials for new LMS certificates.')
	}
	if (!settings.data?.issuing_ready) {
		return settings.data?.issuing_blocker || __('Complete the certificate integration settings.')
	}
	if (settings.data?.last_error) return settings.data.last_error
	return __('New LMS certificates will get a local verifiable credential and QR verification link.')
})

const emptyTitle = computed(() => {
	if (!settings.data?.enabled) return __('Sunbird RC Certificates are disabled')
	if (!settings.data?.issuing_ready) return __('Certificate credential setup is incomplete')
	return __('No verifiable credentials found')
})

const emptyDescription = computed(() => {
	if (!settings.data?.enabled) {
		return __('Enable Sunbird RC Certificates in Integrations before new LMS certificates create credentials.')
	}
	if (!settings.data?.issuing_ready) {
		return settings.data?.issuing_blocker || __('Complete the required settings in Integrations.')
	}
	return __('Issue a new LMS certificate, or regenerate a missing credential for an existing certificate.')
})

const statusTheme = (status) => {
	if (status === 'Issued') return 'green'
	if (status === 'Revoked' || status === 'Failed') return 'red'
	if (status === 'Expired') return 'orange'
	return 'gray'
}

const refresh = () => {
	settings.reload()
	dashboard.reload()
}

const openIntegrations = () => router.push({ name: 'Integrations' })

const copyLink = async (row) => {
	try {
		await navigator.clipboard.writeText(row.verification_url)
	} catch {
		const textarea = document.createElement('textarea')
		textarea.value = row.verification_url
		textarea.setAttribute('readonly', '')
		textarea.style.position = 'fixed'
		textarea.style.opacity = '0'
		document.body.appendChild(textarea)
		textarea.select()
		document.execCommand('copy')
		document.body.removeChild(textarea)
	}
	toast.success(__('Verification link copied'))
}

const openVerification = (row) => {
	window.open(row.verification_url, '_blank')
}

const canRevoke = (row) => {
	return settings.data?.can_configure && row.effective_status === 'Issued'
}

const revokeCredential = (row) => {
	selectedName.value = row.name
	const reason = window.prompt(__('Reason for revocation'), '')
	if (reason === null) return
	revoke.submit({ name: row.name, reason })
}

const regenerateFromPrompt = () => {
	const certificate = window.prompt(__('LMS Certificate ID'))
	if (!certificate) return
	regenerate.submit({ certificate })
}

watch(
	() => ({ ...filters }),
	() => dashboard.reload(),
	{ deep: true }
)

onMounted(() => refresh())

usePageMeta(() => {
	return {
		title: __('Sunbird RC Certificates'),
		icon: brand.favicon,
	}
})
</script>
