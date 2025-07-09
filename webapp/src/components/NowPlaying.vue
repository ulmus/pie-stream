<template>
  <el-card shadow="hover">
    <template #header>
      <span>Now Playing</span>
    </template>
    <div v-if="status.current_playing_album">
      <h3>{{ status.current_playing_album.title }}</h3>
      <p>by {{ status.current_playing_album.artist }}</p>
      <p>State: {{ status.player_state }}</p>
      <el-space>
        <el-button @click="emitStop" type="danger">Stop</el-button>
        <el-button v-if="status.player_state === 'playing'" @click="emitPause">Pause</el-button>
        <el-button v-else @click="emitResume">Resume</el-button>
        <el-button @click="emitPrevious">Previous</el-button>
        <el-button @click="emitNext">Next</el-button>
      </el-space>
    </div>
    <div v-else>
      <p>No album is playing.</p>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { defineProps, defineEmits } from 'vue'
import type { Status } from '../types'
const { status } = defineProps<{ status: Status }>()

const emits = defineEmits<{
  (e: 'stop'): void
  (e: 'pause'): void
  (e: 'resume'): void
  (e: 'previous'): void
  (e: 'next'): void
}>()

const emitStop = () => emits('stop')
const emitPause = () => emits('pause')
const emitResume = () => emits('resume')
const emitPrevious = () => emits('previous')
const emitNext = () => emits('next')
</script>
