import requests
import re
from bs4 import BeautifulSoup
import os
from dotenv import load_dotenv
load_dotenv()
class GeniusLyrics:
    def __init__(self, access_token):
        """
        Initialize the Genius API client
        Get your access token from: https://genius.com/api-clients
        """
        self.access_token = access_token
        self.base_url = "https://api.genius.com"
        self.headers = {
            'Authorization': f'Bearer {self.access_token}',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
    
    def search_song(self, query, limit=10):
        """
        Search for songs using Genius API
        Returns list of song results
        """
        url = f"{self.base_url}/search"
        params = {
            'q': query,
            'per_page': limit
        }
        
        try:
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            data = response.json()
            
            if data['meta']['status'] == 200:
                return data['response']['hits']
            else:
                print(f"API Error: {data['meta']['message']}")
                return []
                
        except requests.exceptions.RequestException as e:
            print(f"Request failed: {e}")
            return []
    
    def get_song_details(self, song_id):
        """
        Get detailed information about a specific song
        """
        url = f"{self.base_url}/songs/{song_id}"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            data = response.json()
            
            if data['meta']['status'] == 200:
                return data['response']['song']
            else:
                print(f"API Error: {data['meta']['message']}")
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"Request failed: {e}")
            return None
    
    def scrape_lyrics(self, song_url):
        """
        Scrape lyrics from Genius song page
        Note: This is necessary because Genius API doesn't provide full lyrics
        """
        try:
            response = requests.get(song_url, headers=self.headers)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find lyrics container (Genius uses different selectors)
            lyrics_containers = soup.select('div[class*="Lyrics__Container"]')
            
            if not lyrics_containers:
                # Try alternative selectors
                lyrics_containers = soup.select('div[data-lyrics-container="true"]')
            
            if not lyrics_containers:
                return "Lyrics not found - page structure may have changed"
            
            lyrics = ""
            for container in lyrics_containers:
                # Remove script and style elements
                for script in container(["script", "style"]):
                    script.decompose()
                
                # Get text and preserve line breaks
                text = container.get_text(separator='\n', strip=True)
                lyrics += text + '\n'
            
            # Clean up the lyrics
            lyrics = re.sub(r'\n\s*\n', '\n\n', lyrics)  # Remove extra blank lines
            lyrics = lyrics.strip()
            
            return lyrics if lyrics else "Could not extract lyrics"
            
        except requests.exceptions.RequestException as e:
            return f"Failed to fetch lyrics: {e}"
        except Exception as e:
            return f"Error parsing lyrics: {e}"
    
    def get_lyrics(self, artist, song_title):
        """
        Main method to get lyrics for a song
        """
        # Search for the song
        artist = ""
        query = f"{artist} {song_title}"
        search_results = self.search_song(query)
        
        if not search_results:
            return {"error": "No search results found"}
        
        # Get the first result (most relevant)
        best_match = search_results[0]['result']
        
        # Get song details
        song_details = self.get_song_details(best_match['id'])
        
        if not song_details:
            return {"error": "Could not fetch song details"}
        
        # Scrape lyrics from the song page
        lyrics = self.scrape_lyrics(song_details['url'])
        
        # Return comprehensive result
        return {
            "title": song_details['title'],
            "artist": song_details['primary_artist']['name'],
            "album": song_details['album']['name'] if song_details['album'] else "Unknown",
            "release_date": song_details['release_date_for_display'],
            "url": song_details['url'],
            "lyrics": lyrics,
            "song_id": song_details['id']
        }
    

# Example usage
def fetch_lyrics(song_name,artist):
    # Replace with your actual Genius API access token
    ACCESS_TOKEN = os.getenv("GENIUS_API_KEY")
    
    # Initialize the client
    genius = GeniusLyrics(ACCESS_TOKEN)
    
    # Example 1: Get lyrics for a specific song
    
    result = genius.get_lyrics(artist,song_name)
    
    if "error" in result:
        print(f"Error: {result['error']}")
        return "Couldn't get lyrics"
        
    else:
        print(f"Title: {result['title']}")
        # print(f"Artist: {result['artist']}")
        # print(f"Album: {result['album']}")
        # print(f"Release Date: {result['release_date']}")
        # print(f"URL: {result['url']}")
        # print("\nLyrics:")
        # print(result['lyrics'])
    
    tex = result['lyrics'].split("Read More")[1:]
    ss = " ".join(tex)
    return ss
