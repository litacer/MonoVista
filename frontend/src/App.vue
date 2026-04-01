<template>
  <div id="app-root">
    <AppNav v-if="!isAdminRoute && !isShareRoute" />
    <main :class="{ 'no-top-padding': isAdminRoute || isShareRoute }">
      <RouterView />
    </main>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import AppNav from '@/components/AppNav.vue'

const route = useRoute()
const isAdminRoute = computed(() => String(route.path).startsWith('/admin'))
const isShareRoute  = computed(() => String(route.path).startsWith('/share'))
</script>

<style scoped>
#app-root {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}
main {
  flex: 1;
  padding-top: 64px;
}
.no-top-padding {
  padding-top: 0;
}
</style>
