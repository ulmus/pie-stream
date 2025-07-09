<script setup lang="ts">
import { ref, onMounted } from 'vue'
import NowPlaying from './components/NowPlaying.vue'
import AlbumList from './components/AlbumList.vue'
import {
  getAlbums,
  getStatus,
  playAlbum,
  stopPlayback,
  pausePlayback,
  resumePlayback,
  nextTrack,
  previousTrack,
} from './api'
import type { Album, Status } from './types'

// state
const albums = ref<Album[]>([])
const status = ref<Status>({ current_playing_album: null, player_state: '', is_connected: false })

// load functions
async function loadAlbums() {
  albums.value = await getAlbums()
}
async function loadStatus() {
  status.value = await getStatus()
}

// event handlers
async function handlePlay(index: number) {
  await playAlbum(index)
  await loadStatus()
}
async function handleStop() {
  await stopPlayback()
  await loadStatus()
}
async function handlePause() {
  await pausePlayback()
  await loadStatus()
}
async function handleResume() {
  await resumePlayback()
  await loadStatus()
}
async function handleNext() {
  await nextTrack()
  await loadStatus()
}
async function handlePrevious() {
  await previousTrack()
  await loadStatus()
}

onMounted(() => {
  loadAlbums()
  loadStatus()
  setInterval(loadStatus, 5000)
})
</script>

<template>
  <el-container style="padding: 20px">
    <el-header>
      <h1>Music Player</h1>
    </el-header>
    <el-main>
      <el-row :gutter="20">
        <el-col :span="12">
          <NowPlaying
            :status="status"
            @stop="handleStop"
            @pause="handlePause"
            @resume="handleResume"
            @next="handleNext"
            @previous="handlePrevious"
          />
        </el-col>
        <el-col :span="12">
          <AlbumList :albums="albums" @play="handlePlay" />
        </el-col>
      </el-row>
    </el-main>
  </el-container>
</template>

<style scoped>
h1 {
  margin: 0;
  font-size: 24px;
}
</style>
