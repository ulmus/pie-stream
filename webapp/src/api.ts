import axios from 'axios';
import type { Album, Status } from './types';

const api = axios.create({
  baseURL: '/api',
});

export async function getAlbums(): Promise<Album[]> {
  const response = await api.get<Album[]>('/albums');
  return response.data;
}

export async function getStatus(): Promise<Status> {
  const response = await api.get<Status>('/status');
  return response.data;
}

export async function playAlbum(index: number): Promise<Album> {
  const response = await api.post<{ album: Album }>('/play', index, {
    headers: { 'Content-Type': 'application/json' },
  });
  return response.data.album;
}

export async function stopPlayback(): Promise<void> {
  await api.post('/stop');
}

export async function pausePlayback(): Promise<void> {
  await api.post('/pause');
}

export async function resumePlayback(): Promise<void> {
  await api.post('/resume');
}

export async function nextTrack(): Promise<void> {
  await api.post('/next_track');
}

export async function previousTrack(): Promise<void> {
  await api.post('/previous_track');
}
