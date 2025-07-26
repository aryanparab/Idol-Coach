import os
import json
import unicodedata
import re
from typing import List, Dict, Optional, Any
from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database
from dotenv import load_dotenv

load_dotenv()

class MongoHandler:
    def __init__(self):
        self.client = None
        self.db = None
        self.songs_collection = None
        self._connect()
    
    def _connect(self):
        """Establish connection to MongoDB"""
        try:
            self.client = MongoClient(os.getenv("MONGODB_URI"))
            self.db = self.client[os.getenv("MONGODB_DB")]
            self.songs_collection = self.db["songs_db"]
        except Exception as e:
            raise Exception(f"Failed to connect to MongoDB: {e}")
    
    def get_all_songs(self) -> List[Dict[str, Any]]:
        """Get all songs from the database"""
        try:
            songs = list(self.songs_collection.find({}, {"_id": 0}))
            return songs
        except Exception as e:
            raise Exception(f"Error fetching all songs: {e}")
    
    def get_song_by_title(self, title: str, exact_match: bool = False) -> Optional[Dict[str, Any]]:
        """
        Get a song by title
        
        Args:
            title (str): Song title to search for
            exact_match (bool): If True, search for exact match. If False, use regex for partial match
        
        Returns:
            Dict or None: Song data if found, None otherwise
        """
        try:
            normalized_title = self.normalize_text(title)
            
            if exact_match:
                query = {"normalized_title": normalized_title}
            else:
                query = {"normalized_title": {"$regex": normalized_title, "$options": "i"}}
            
            song = self.songs_collection.find_one(query, {"_id": 0})
            return song
        except Exception as e:
            raise Exception(f"Error fetching song by title '{title}': {e}")
    
    def get_song_by_normalized_title(self, normalized_title: str) -> Optional[Dict[str, Any]]:
        """Get a song by its normalized title"""
        try:
            song = self.songs_collection.find_one(
                {"normalized_title": {"$regex": normalized_title}}, 
                {"_id": 0}
            )
            print(song)
            return song
        except Exception as e:
            raise Exception(f"Error fetching song by normalized title '{normalized_title}': {e}")
    
    def insert_song(self, song_data: Dict[str, Any]) -> bool:
        """
        Insert a single song into the database
        
        Args:
            song_data (dict): Song data to insert
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Add normalized title if not present
            if "normalized_title" not in song_data and "title" in song_data:
                song_data["normalized_title"] = self.normalize_text(song_data["title"])
            
            result = self.songs_collection.insert_one(song_data)
            return result.acknowledged
        except Exception as e:
            raise Exception(f"Error inserting song: {e}")
    
    def insert_multiple_songs(self, songs_data: List[Dict[str, Any]]) -> bool:
        """
        Insert multiple songs into the database
        
        Args:
            songs_data (list): List of song data dictionaries
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Add normalized titles if not present
            for song in songs_data:
                if "normalized_title" not in song and "title" in song:
                    song["normalized_title"] = self.normalize_text(song["title"])
            
            result = self.songs_collection.insert_many(songs_data)
            return result.acknowledged
        except Exception as e:
            raise Exception(f"Error inserting multiple songs: {e}")
    
    def update_song(self, title: str, update_data: Dict[str, Any]) -> bool:
        """
        Update a song by title
        
        Args:
            title (str): Song title to update
            update_data (dict): Data to update
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            normalized_title = self.normalize_text(title)
            result = self.songs_collection.update_one(
                {"normalized_title": normalized_title},
                {"$set": update_data}
            )
            return result.modified_count > 0
        except Exception as e:
            raise Exception(f"Error updating song '{title}': {e}")
    
    def delete_song(self, title: str) -> bool:
        """
        Delete a song by title
        
        Args:
            title (str): Song title to delete
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            normalized_title = self.normalize_text(title)
            result = self.songs_collection.delete_one({"normalized_title": normalized_title})
            return result.deleted_count > 0
        except Exception as e:
            raise Exception(f"Error deleting song '{title}': {e}")
    
    def song_exists(self, title: str) -> bool:
        """
        Check if a song exists in the database
        
        Args:
            title (str): Song title to check
            
        Returns:
            bool: True if song exists, False otherwise
        """
        try:
            normalized_title = self.normalize_text(title)
            count = self.songs_collection.count_documents({"normalized_title": normalized_title})
            return count > 0
        except Exception as e:
            raise Exception(f"Error checking if song exists '{title}': {e}")
    
    def search_songs(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Search songs by title or artist
        
        Args:
            query (str): Search query
            limit (int): Maximum number of results
            
        Returns:
            List[Dict]: List of matching songs
        """
        try:
            normalized_query = self.normalize_text(query)
            songs = list(self.songs_collection.find(
                {
                    "$or": [
                        {"normalized_title": {"$regex": normalized_query, "$options": "i"}},
                        {"artist": {"$regex": query, "$options": "i"}}
                    ]
                },
                {"_id": 0}
            ).limit(limit))
            return songs
        except Exception as e:
            raise Exception(f"Error searching songs with query '{query}': {e}")
    
    def load_songs_from_json(self, json_file_path: str) -> bool:
        """
        Load songs from a JSON file into the database
        
        Args:
            json_file_path (str): Path to the JSON file
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            with open(json_file_path, 'r', encoding='utf-8') as f:
                songs_data = json.load(f)
            
            # Add normalized titles and insert only if not already present
            inserted_count = 0
            for song in songs_data:
                if "normalized_title" not in song and "title" in song:
                    song["normalized_title"] = self.normalize_text(song["title"])
                
                # Check if song already exists
                if not self.song_exists(song["title"]):
                    self.songs_collection.insert_one(song)
                    inserted_count += 1
            
            print(f"Successfully inserted {inserted_count} new songs from {json_file_path}")
            return True
        except Exception as e:
            raise Exception(f"Error loading songs from JSON file '{json_file_path}': {e}")
    
    @staticmethod
    def normalize_text(text: str) -> str:
        """
        Normalize text for consistent searching
        
        Args:
            text (str): Text to normalize
            
        Returns:
            str: Normalized text
        """
        if not text:
            return ""
        
        text = text.lower()
        text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')
        text = re.sub(r'[^\w\s]', '', text)  # Remove punctuation
        text = ' '.join(text.split())  # Remove extra spaces
        print(text)
        return text
    
    def close_connection(self):
        """Close the MongoDB connection"""
        if self.client:
            self.client.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close_connection()


# Convenience functions for direct usage
def get_mongo_handler() -> MongoHandler:
    """Get a MongoHandler instance"""
    return MongoHandler()

def get_all_songs() -> List[Dict[str, Any]]:
    """Get all songs - convenience function"""
    with MongoHandler() as handler:
        return handler.get_all_songs()

def get_song(title: str, exact_match: bool = False) -> Optional[Dict[str, Any]]:
    """Get a song by title - convenience function"""
    with MongoHandler() as handler:
        return handler.get_song_by_title(title, exact_match)

def insert_song(song_data: Dict[str, Any]) -> bool:
    """Insert a song - convenience function"""
    with MongoHandler() as handler:
        return handler.insert_song(song_data)

def song_exists(title: str) -> bool:
    """Check if song exists - convenience function"""
    with MongoHandler() as handler:
        return handler.song_exists(title)

def search_songs(query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Search songs - convenience function"""
    with MongoHandler() as handler:
        return handler.search_songs(query, limit)


if __name__ == "__main__":
    # Example usage and testing
    try:
        # Initialize handler
        handler = MongoHandler()
        
        # Load songs from JSON file (optional)
        # handler.load_songs_from_json('songs/songs_db.json')
        
        # Test getting all songs
        all_songs = handler.get_all_songs()
        print(f"Total songs in database: {len(all_songs)}")
        
        # Test search functionality
        if all_songs:
            sample_song = all_songs[0]
            print(f"Sample song: {sample_song.get('title', 'Unknown')}")
            
            # Test getting specific song
            found_song = handler.get_song_by_title(sample_song.get('title', ''))
            print(f"Found song: {found_song is not None}")
        
        handler.close_connection()
        print("MongoDB operations completed successfully!")
        
    except Exception as e:
        print(f"Error during MongoDB operations: {e}")