const BASE_URL = "http://localhost:8000"; // Change if using a deployed backend

export async function fetchSongs() {
  const res = await fetch(`${BASE_URL}/songs/list`);
  return res.json();
}

export async function prepareSong(songName) {
  const res = await fetch(`${BASE_URL}/songs/prepare`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ song_name: songName }),
  });
  return res.json();
}

export async function analyzeUserAudio(formData) {
  try {
    const res = await fetch(`${BASE_URL}/user/analyze`, {
      method: "POST",
      body: formData,
      mode: 'cors',
    });
    console.log(res)
    return res;
  } catch (error) {
    console.error('API fetch error:', error);
    throw error;
  }
}


export async function analyzeUserText(formData) {
  try {
    const res = await fetch(`${BASE_URL}/user/analyze_text`, {
      method: "POST",
      body: formData,
      mode: 'cors',
    });
    console.log(res)
    return res;
  } catch (error) {
    console.error('API fetch error:', error);
    throw error;
  }
}

export async function getSongDetails(song){

  try {
    const res = await fetch(`${BASE_URL}/songs/get_song`, {
      method: "POST",
      body: JSON.stringify({song_name : song}),
      headers: { "Content-Type": "application/json" },
    });
    console.log(res)
    return res;
  } catch (error) {
    console.error('API fetch error:', error);
    throw error;
  }
}