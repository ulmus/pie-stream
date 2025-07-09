<template>
  <el-card shadow="hover">
    <template #header>
      <span>Albums</span>
    </template>
    <el-list>
      <el-list-item v-for="(album, index) in albums" :key="album.id">
        <el-space>
          <span>{{ album.title }} by {{ album.artist }}</span>
          <el-button size="mini" @click="emitPlay(index)">Play</el-button>
        </el-space>
      </el-list-item>
    </el-list>
  </el-card>
</template>

<script setup lang="ts">
import { defineProps, defineEmits } from 'vue';
import type { Album } from '../types';
const { albums } = defineProps<{ albums: Album[] }>();
const emits = defineEmits<(e: 'play', index: number) => void>();

const emitPlay = (index: number) => emits('play', index);
</script>
