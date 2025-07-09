export interface Track {
  title: string;
  duration: number;
  index: number;
}

export interface Album {
  id: number;
  title: string;
  artist: string;
  tracks: Track[];
}

export interface Status {
  current_playing_album: Album | null;
  player_state: string;
  is_connected: boolean;
}
