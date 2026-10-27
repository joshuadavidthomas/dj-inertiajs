<script setup lang="ts">
import { router, useHttp, usePage } from '@inertiajs/vue3'

const page = usePage<Record<string, unknown>>()

const http = useHttp({})

function reloadLocale() {
  router.reload({ only: ['config.locale'] })
}

function postVisit() {
  router.post('/v3/post/')
}

function postHttp() {
  http.post('/v3/post/')
}
</script>

<template>
  <main>
    <h1>Inertia Django v3 compatibility</h1>
    <pre data-testid="props">{{ JSON.stringify(page.props) }}</pre>
    <button type="button" @click="reloadLocale">Reload locale</button>
    <button type="button" @click="postVisit">Post visit</button>
    <button type="button" @click="postHttp">Post with useHttp</button>
  </main>
</template>
