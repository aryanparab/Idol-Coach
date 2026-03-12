# IDOL COACH - Interview Answers with Code References

## Technical Implementation Questions

---

### Q1: "Walk me through how you aligned user vocals with original lyrics using the Gentle API. What challenges did you face with timing synchronization?"

**Answer Structure:**

**Gentle API Integration** (`scripts_user/lyric_matcher.py:1-25`):
```
The Gentle API provides word-level timestamp alignments for audio. Here's the implementation:

1. Loading Gentle alignments:
   def load_gentle_alignment(gentle_json_path: str) -> List[Dict]:
       with open(gentle_json_path, 'r') as f:
           data = json.load(f)
       return data  # Returns list of words with start/end times

2. Each word entry contains:
   {
     "word": "hello",
     "start": 0.5,  # seconds
     "end": 0.8
   }
```

**Challenges with Timing Synchronization**:

1. **Variable User Pacing**:
   - Users sing at different tempos than the original artist
   - Solution: `find_best_segment_match()` function tries multiple segment lengths

2. **Finding the Matching Segment** (`lyric_matcher.py:79-147`):
   ```python
   def find_best_segment_match(song_words, user_words, full_song_alignment):
       # Tries different segment lengths to find best match
       for multiplier in [1.0, 1.2, 0.8, 1.5, 1.8, 0.6, 2.0, 2.5]:
           length = int(user_word_count * multiplier)
           # Slide window across song and calculate confidence
   ```

3. **Fuzzy Matching for Timing Variations** (`lyric_matcher.py:44-77`):
   ```python
   def calculate_sequence_similarity(user_words, song_segment):
       # Strategy 1: Subsequence matching (words in order) - 50% weight
       # Strategy 2: Fuzzy string matching - 30% weight  
       # Strategy 3: Word coverage - 20% weight
       fuzzy_scores = [
           fuzz.ratio(user_text, segment_text),        # Character-level
           fuzz.partial_ratio(user_text, segment_text), # Partial match
           fuzz.token_sort_ratio(user_text, segment_text), # Order-independent
           fuzz.token_set_ratio(user_text, segment_text)  # Set-based
       ]
   ```

4. **Preprocessing for Singing** (`lyric_matcher.py:25-43`):
   ```python
   def preprocess_lyrics(text):
       # Remove filler words common in singing
       fillers = ['uh', 'um', 'ah', 'oh', 'yeah', 'hey', 'mmm']
       # Handle singing variations
       replacements = {
           "gonna": "going to",
           "wanna": "want to",
           # ...
       }
   ```

**Key Insight**: The system doesn't expect perfect timing - it finds the best matching segment using a combination of fuzzy text matching and confidence scores, allowing for natural variations in user singing.

---

### Q2: "You mentioned using Librosa to extract audio features. Which specific features did you extract (MFCCs, spectral features, pitch) and why?"

**Complete Feature List** (`scripts_user/audio_analysis.py:181-227`):

```python
def extract_comprehensive_features(self, y):
    features = {}
    
    # === BASIC FEATURES ===
    
    # 1. MFCCs (13 coefficients)
    mfcc = librosa.feature.mfcc(y=y, sr=self.sr, n_mfcc=13)
    features["mfcc_mean"] = np.mean(mfcc, axis=1)  # Timbre signature
    features["mfcc_std"] = np.std(mfcc, axis=1)    # Timbre variation
    
    # WHY: MFCCs capture the spectral envelope of the voice
    # Each singer has a unique MFCC "fingerprint"
    # Used for: Voice identity, comparing timbre to original
    
    # 2. Chroma Features
    chroma = librosa.feature.chroma_stft(y=y, sr=self.sr)
    features["chroma_mean"] = np.mean(chroma, axis=1)  # Harmonic content
    features["chroma_std"] = np.std(chroma, axis=1)
    
    # WHY: Chroma represents pitch classes (C, C#, D, etc.)
    # Essential for detecting which musical notes are being sung
    # Used for: Harmony analysis, pitch accuracy
    
    # 3. Spectral Centroid
    features["spectral_centroid"] = np.mean(librosa.feature.spectral_centroid(y=y, sr=self.sr))
    
    # WHY: Perceptual "brightness" of the sound
    Higher values = brighter/tenser sound
    Used for: Vocal focus, clarity assessment
    
    # 4. Spectral Bandwidth
    features["spectral_bandwidth"] = np.mean(librosa.feature.spectral_bandwidth(y=y, sr=self.sr))
    
    # WHY: Width of the frequency spectrum
    Related to: Voice richness and body
    
    # 5. Spectral Flatness
    features["spectral_flatness"] = np.mean(librosa.feature.spectral_flatness(y=y))
    
    # WHY: Distinguishes tonal (voiced) from noise-like sounds
    Used for: Detecting breath sounds vs. sustained notes
    
    # 6. Zero Crossing Rate
    features["zcr"] = np.mean(librosa.feature.zero_crossing_rate(y))
    
    # WHY: Rate of sign changes in the signal
    Useful for: Percussive onsets, voice/unvoice boundaries
    
    # 7. RMS Energy
    features["rms"] = np.mean(librosa.feature.rms(y=y))
    
    # WHY: Loudness/intensity over time
    Critical for: Dynamics and expression analysis

    # === ADVANCED VOICE-SPECIFIC FEATURES ===
    
    # 8. Pitch Contour (librosa.piptrack)
    f0, voiced_flag, voiced_probs = librosa.pyin(
        y, fmin=80, fmax=800, sr=self.sr
    )
    
    # WHY: Fundamental frequency (F0) over time
    The most important feature for pitch accuracy
    Used for: DTW comparison, intonation measurement
    
    # 9. Vibrato Analysis
    def analyze_vibrato(self, pitch_contour):
        # Rate: Oscillations per second (ideal: 5-7 Hz)
        # Extent: Pitch variation in cents/semitones
        # Regularity: Consistency of oscillations
    
    # WHY: Professional singing technique indicator
    Shows breath support and vocal control
    
    # 10. Formant Analysis (via spectral contrast)
    def analyze_formants(self, y):
        spectral_contrast = librosa.feature.spectral_contrast(y=y, sr=self.sr)
        # Formants determine vowel quality
        # F1, F2, F3 frequencies characterize different vowels
    
    # WHY: Vowel clarity and voice quality
    Different formants = different vowel shapes
    
    # 11. Onset Detection
    onset_frames = librosa.onset.onset_detect(y=y, sr=self.sr, units='frames')
    onset_strength = librosa.onset.onset_strength(y=y, sr=self.sr)
    
    # WHY: How cleanly notes start
    Precision of attack affects perceived skill level
    
    # 12. Dynamics Analysis
    rms = librosa.feature.rms(y=y, frame_length=2048, hop_length=self.hop_length)[0]
    dynamic_range = np.max(rms) - np.min(rms)
    expression_variation = np.std(gaussian_filter1d(rms, sigma=3))
    
    # WHY: Dynamic range = musical expression
    Too flat = boring performance
    Too erratic = poor control
    
    # 13. Pitch Stability
    def analyze_pitch_stability(self, pitch_contour):
        # Pitch drift: Gradual change over time (poor)
        # Stability: Variation around mean (higher = more stable)
        # Intonation: Distance to nearest semitone (in cents)
    
    # WHY: Professional singers maintain stable pitch
    Amateur singers tend to drift
    
    # 14. Vocal Fry Detection
    def detect_vocal_fry(self, y):
        # Analyze low-frequency energy and irregularity
        # Fry = very low pitch (<100Hz) with high irregularity
    
    # WHY: Voice health indicator
    Too much fry = poor technique or fatigue
    
    # 15. Breath Detection
    def detect_breath_segments(self, y):
        rms = librosa.feature.rms(y=y)[0]
        # Find low-energy segments that could be breaths
        threshold = np.mean(rms_smooth) * 0.3
        
    # WHY: Breath timing and efficiency
    Professional singers take efficient breaths
```

**Feature Selection Rationale**:
- **MFCCs**: Voice identity and timbre comparison
- **Pitch**: Primary metric for accuracy (DTW)
- **Spectral**: Quality and clarity assessment
- **Dynamics**: Musical expression
- **Advanced voice features**: Professional technique indicators

---

### Q3: "How did you handle the comparison between user singing and original vocals? What mathematical metrics did you use?"

**Answer Structure** (`scripts_user/compare_pitch_dtw.py`, `scripts_user/audio_analysis.py`):

#### A. Pitch Comparison using DTW

```python
# DTW (Dynamic Time Warping) - The primary comparison metric
def compare_with_dtw(user_pitch, ref_pitch):
    user_pitch = user_pitch.reshape(-1, 1)
    ref_pitch = ref_pitch.reshape(-1, 1)
    
    alignment = dtw(
        user_pitch, ref_pitch, 
        keep_internals=True  # Keep path and cost matrix
    )
    
    return {
        "distance": alignment.normalizedDistance,  # Normalized DTW distance
        "path": alignment.index1s,  # Alignment path
        "cost_matrix": alignment.costMatrix  # Cost matrix for visualization
    }
```

**Why DTW?**
- Handles tempo differences between user and original
- Finds optimal alignment between two sequences
- Returns normalized distance (0 = perfect match)
- `alignment_quality = 1.0 / (1.0 + dtw_result["distance"])`

#### B. Feature Vector Comparison

```python
from scipy.spatial.distance import cosine

def compare_comprehensive_features(self, user_feat, ref_feat):
    comparison = {}
    
    for key in user_feat:
        if key not in ref_feat:
            continue
            
        if isinstance(user_feat[key], np.ndarray):
            # Cosine distance for vectors (MFCCs, chroma, etc.)
            comparison[key + "_cosine_difference"] = cosine(
                user_feat[key], 
                ref_feat[key]
            )
        else:
            # Absolute difference for scalars
            comparison[key + "_abs_diff"] = abs(user_feat[key] - ref_feat[key])
            
            # Relative difference for percentage feedback
            if ref_feat[key] != 0:
                comparison[key + "_relative_diff"] = (user_feat[key] - ref_feat[key]) / ref_feat[key]
```

**Cosine Distance**: Measures angle between vectors, perfect for comparing:
- MFCC vectors (timbre)
- Chroma vectors (harmony)
- Spectral contrast (tone quality)

#### C. Word-Level Pitch Accuracy (Cents)

```python
# Convert pitch to cents for musical accuracy measurement
def analyze_word_level_performance(self, user_pitch, ref_pitch):
    # Convert to cents from A4 (440 Hz)
    user_cents = 1200 * np.log2(user_pitch_clean / 440)
    ref_cents = 1200 * np.log2(ref_pitch_clean / 440)
    
    pitch_diff = np.mean(user_cents) - np.mean(ref_cents)
    
    # 100 cents = 1 semitone
    # < 50 cents = good accuracy
    # > 100 cents = noticeable pitch issue
    if abs(pitch_diff) > tolerance_cents:  # tolerance_cents = 50
        direction = "sharp" if pitch_diff > 0 else "flat"
        cents_off = abs(pitch_diff)
```

#### D. Lyric Matching with Fuzzy String Matching

```python
from fuzzywuzzy import fuzz

def calculate_sequence_similarity(user_words, song_segment):
    # Weighted combination of similarity metrics
    
    # 1. Subsequence matching (words in order) - 50% weight
    matches_in_order = 0
    for segment_word in segment_word_list:
        if fuzz.ratio(user_word_list[user_idx], segment_word) > 80:
            matches_in_order += 1
            user_idx += 1
    subsequence_score = matches_in_order / len(user_word_list)
    
    # 2. Fuzzy string matching - 30% weight
    fuzzy_scores = [
        fuzz.ratio(user_text, segment_text),        # Exact char match
        fuzz.partial_ratio(user_text, segment_text), # Partial substring
        fuzz.token_sort_ratio(user_text, segment_text),  # Order-independent
        fuzz.token_set_ratio(user_text, segment_text)   # Set-based
    ]
    fuzzy_average = sum(fuzzy_scores) / len(fuzzy_scores) / 100.0
    
    # 3. Word coverage - 20% weight
    user_words_found = sum(
        1 for user_word in user_word_list
        if any(fuzz.ratio(user_word, sw) > 70 for sw in segment_word_list)
    )
    coverage_score = user_words_found / len(user_word_list)
    
    final_score = subsequence_score * 0.5 + fuzzy_average * 0.3 + coverage_score * 0.2
    
    return final_score
```

**Summary of Mathematical Metrics**:

| Metric | Type | Use Case |
|--------|------|----------|
| DTW Distance | Dynamic Time Warping | Pitch contour comparison |
| Euclidean Distance | L2 norm | Frame-by-frame pitch in DTW |
| Cosine Distance | Vector similarity | Feature vectors (MFCC, chroma) |
| Absolute Difference | L1 norm | Scalar feature comparison |
| Relative Difference | Percentage | Performance feedback |
| Cents Deviation | Logarithmic | Pitch accuracy in musical terms |
| Fuzzy Ratios | String similarity | Lyric matching |

---

### Q4: "Explain your approach to reducing inference latency by 30%. What was the bottleneck?"

**Analysis of Current Pipeline** (`process_user_audio.py:34-85`):

```
Current Sequential Flow:
1. Load gentle alignment (fast - file read)
2. Transcribe with Whisper (SLOW - ~3-5 seconds)
3. Extract user pitch contour (medium - ~1-2 seconds)
4. Extract reference pitch contour (medium - ~1-2 seconds)
5. Find matching segment (fast - ~0.1 seconds)
6. Segment reference audio (fast - ~0.1 seconds)
7. Analyze audio features (medium - ~1-2 seconds)
8. Generate AI feedback (medium - ~1-2 seconds)

Total estimated time: ~8-15 seconds
```

**Identified Bottlenecks**:

1. **Whisper Transcription** (~40% of time):
   - Using large model (likely "base" or "medium")
   - Sequential processing

2. **Pitch Extraction** (25% of time):
   - Extracted twice (user + reference)
   - No caching of reference features

3. **Feature Analysis** (20% of time):
   - Computing many features per frame
   - Granular word-by-word analysis

4. **Sequential Dependencies** (15% of time):
   - Can't parallelize due to dependencies

**30% Latency Reduction Plan**:

#### Optimization 1: Parallel Processing
```python
# BEFORE (sequential):
user_pitch = extract_pitch_contour(user_audio_path)  # 2s
ref_pitch = extract_pitch_contour(reference_audio_path)  # 2s

# AFTER (parallel):
import concurrent.futures
with concurrent.futures.ThreadPoolExecutor() as executor:
    user_future = executor.submit(extract_pitch_contour, user_audio_path)
    ref_future = executor.submit(extract_pitch_contour, reference_audio_path)
    user_pitch = user_future.result()
    ref_pitch = ref_future.result()

# Time savings: 2s → ~0.1s (parallel)
# Improvement: ~15% overall
```

#### Optimization 2: Feature Caching
```python
# Cache reference song features (computed once, used many times)
reference_features_cache = {}

def get_reference_features(song_id):
    if song_id not in reference_features_cache:
        # Compute once
        reference_features_cache[song_id] = compute_features(reference_audio)
    return reference_features_cache[song_id]

# Time savings: Avoid recomputing reference features
# Improvement: ~20% overall
```

#### Optimization 3: Whisper Model Optimization
```python
# BEFORE: Whisper large model
whisper_model = whisper.load_model("medium")  # ~769M parameters

# AFTER: Whisper small model with optimizations
whisper_model = whisper.load_model("tiny")  # ~39M parameters
# Or: Use ONNX runtime for faster inference
# Or: Batch process multiple requests

# Time savings: 3-5s → 0.5-1s
# Improvement: ~25% overall
```

#### Optimization 4: Early Termination
```python
# Only do granular analysis if overall match is good
if match["confidence"] < 0.3:
    return {
        "matched_lyrics": match["song_words_snippet"],
        "confidence": match["confidence"],
        "feedback": "No good match found - try again"
    }
    # Skip expensive feature analysis
    return

# Time savings: Skip ~1-2s of processing for bad matches
# Improvement: ~10% average (depending on match rate)
```

#### Optimization 5: Reduced Feature Set
```python
# BEFORE: Full feature extraction (~20 features)
features = extract_comprehensive_features(y)  # ~2s

# AFTER: Essential features only for matching (~8 features)
features = extract_essential_features(y)  # ~0.5s
# Full analysis only for matched segments

# Time savings: ~1.5s per analysis
# Improvement: ~10% overall
```

**Combined Impact**:
- Parallel processing: ~15%
- Feature caching: ~20%
- Whisper optimization: ~25%
- Early termination: ~10%
- Reduced feature set: ~10%

**Total: ~80% reduction (exceeds 30% goal)**

---

### Q5: "Why did you choose both PostgreSQL and MongoDB? What data went where?"

**Current Implementation Analysis**:

#### MongoDB (`scripts/agents.py:72-85`):
```python
client = MongoClient(os.getenv('MONGODB_URI', 'mongodb://localhost:27017'))
db = client[os.getenv("MONGODB_DB")]
chats_collection = db.chats

# Used for:
# 1. Chat history with flexible schema
# 2. Singing session data with variable structure
# 3. User feedback documents
```

**What goes to MongoDB**:
| Collection | Data Type | Reason |
|------------|-----------|--------|
| `chats` | Chat messages, timestamps, voice recordings | Flexible schema, chat-centric access |
| `singing_sessions` | Analysis results, feedback, recordings | Variable structure per session |
| `user_preferences` | Coaching level, skill progress | Document-based, frequent updates |

**Why MongoDB?**
1. **Flexible Schema**: Each singing session can have different analysis results
2. **Chat-Centric Access**: Natural fit for conversation history
3. **Fast Writes**: Append-only chat messages
4. **Complex Documents**: Feedback can include nested arrays, objects

#### PostgreSQL (Recommended but not implemented):
```sql
-- What SHOULD go to PostgreSQL:

-- Songs table
CREATE TABLE songs (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    artist VARCHAR(255),
    genre VARCHAR(100),
    difficulty VARCHAR(20),
    duration_seconds INTEGER,
    gentle_alignment_path VARCHAR(500),
    reference_audio_path VARCHAR(500),
    created_at TIMESTAMP DEFAULT NOW()
);

-- User performance metrics
CREATE TABLE user_performance (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    song_id INTEGER REFERENCES songs(id),
    pitch_accuracy DECIMAL(5,4),
    vocal_stability DECIMAL(5,4),
    breath_support DECIMAL(5,4),
    recorded_at TIMESTAMP DEFAULT NOW()
);

-- Analytics aggregates
CREATE TABLE daily_metrics (
    date DATE PRIMARY KEY,
    total_sessions INTEGER,
    avg_pitch_accuracy DECIMAL(5,4),
    active_users INTEGER
);
```

**What goes to PostgreSQL**:
| Table | Data Type | Reason |
|-------|-----------|--------|
| `songs` | Song metadata, paths, difficulty | Structured, frequent joins |
| `user_performance` | Metrics over time | ACID for tracking progress |
| `analytics` | Aggregates, statistics | SQL for complex queries |
| `user_accounts` | Authentication, settings | Relational integrity |

**Why PostgreSQL?**
1. **Structured Data**: Songs, users, relationships
2. **Complex Queries**: Aggregations, JOINs for analytics
3. **ACID Compliance**: Critical for performance tracking
4. **Indexing**: Fast lookups by song, user, date

#### Hybrid Data Placement Strategy:

```
┌─────────────────────────────────────────────────────────┐
│                    APPLICATION                          │
└─────────────────────┬───────────────────────────────────┘
                      │
          ┌───────────┴───────────┐
          │                       │
    ┌─────▼─────┐           ┌─────▼─────┐
    │  MongoDB  │           │PostgreSQL │
    │(Flexible) │           │(Structured)│
    └───────────┘           └───────────┘
          │                       │
    ┌─────┴─────┐           ┌─────┴─────┐
    │ Chat logs │           │ Song      │
    │ Sessions  │           │ metadata  │
    │ Feedback  │           │ Analytics │
    │ Preferences           │ User data │
```

**Data Flow Example**:
```python
# When user completes a singing session:
def save_session(user_id, audio_data, analysis_results):
    # Structured data → PostgreSQL
    db.execute("""
        INSERT INTO user_performance 
        (user_id, song_id, pitch_accuracy, vocal_stability, recorded_at)
        VALUES (%s, %s, %s, %s, NOW())
    """, user_id, song_id, analysis['pitch_accuracy'], analysis['stability'])
    
    # Flexible document → MongoDB
    chats_collection.insert_one({
        'user_id': user_id,
        'timestamp': datetime.now(),
        'recording': audio_url,
        'analysis': analysis_results,
        'feedback': coach_feedback
    })
```

---

## System Design Questions

---

### Q6: "How would you scale this system to handle 10,000 concurrent users?"

**Architecture Design**:

#### Current Limitations:
- Synchronous processing in `process_user_audio.py`
- No caching layer
- Single database instance
- No horizontal scaling

#### Scaled Architecture:

```
                              ┌─────────────────────────┐
                              │   CDN (CloudFront)      │
                              │   (Audio Caching)       │
                              └───────────┬─────────────┘
                                          │
                              ┌───────────▼─────────────┐
                              │   Load Balancer         │
                              │   (ALB/NGINX)           │
                              │   - Round robin         │
                              │   - Health checks       │
                              └───────────┬─────────────┘
                                          │
              ┌───────────────────────────┼───────────────────────────┐
              │                           │                           │
    ┌─────────▼─────────┐       ┌─────────▼─────────┐       ┌─────────▼─────────┐
    │  API Server 1     │       │  API Server 2     │       │  API Server N     │
    │  (Stateless)      │       │  (Stateless)      │       │  (Stateless)      │
    │  - FastAPI/Flask  │       │  - FastAPI/Flask  │       │  - FastAPI/Flask  │
    └─────────┬─────────┘       └─────────┬─────────┘       └─────────┬─────────┘
              │                           │                           │
              └───────────────────────────┼───────────────────────────┘
                                          │
                              ┌───────────▼─────────────┐
                              │   Message Queue         │
                              │   (Redis/RabbitMQ)      │
                              │   - Distribute work     │
                              │   - Load balancing      │
                              └───────────┬─────────────┘
                                          │
              ┌───────────────────────────┼───────────────────────────┐
              │                           │                           │
    ┌─────────▼─────────┐       ┌─────────▼─────────┐       ┌─────────▼─────────┐
    │  Worker 1         │       │  Worker 2         │       │  Worker N         │
    │  - Audio process  │       │  - Audio process  │       │  - Audio process  │
    │  - Pitch extract  │       │  - Pitch extract  │       │  - Pitch extract  │
    │  - Feature anal   │       │  - Feature anal   │       │  - Feature anal   │
    └─────────┬─────────┘       └─────────┬─────────┘       └─────────┬─────────┘
              │                           │                           │
              └───────────────────────────┼───────────────────────────┘
                                          │
              ┌───────────────────────────┼───────────────────────────┐
              │                           │                           │
    ┌─────────▼─────────┐       ┌─────────▼─────────┐       ┌─────────▼─────────┐
    │  Redis            │       │  PostgreSQL       │       │  MongoDB          │
    │  (Cache)          │       │  (Primary +       │       │  (Sharded)        │
    │  - Session cache  │       │   Replicas)       │       │  - Chat logs      │
    │  - Feature cache  │       │  - Songs          │       │  - Sessions       │
    │  - Rate limiting  │       │  - Analytics      │       │  - Feedback       │
    └───────────────────┘       └───────────────────┘       └───────────────────┘
                                          │
                              ┌───────────▼─────────────┐
                              │   S3 Storage            │
                              │  - User recordings      │
                              │  - Reference audio      │
                              │  - Analysis results     │
                              └─────────────────────────┘
```

#### Scaling Components:

**1. API Servers (Horizontal Scaling)**:
```python
# Stateless design allows horizontal scaling
from fastapi import FastAPI
app = FastAPI()

# No local state - all in Redis/database
# Deploy with Docker/Kubernetes
# Auto-scale based on CPU/latency metrics

# Target: 10 instances × 1000 requests/instance = 10,000 concurrent
```

**2. Async Workers (Processing Queue)**:
```python
# Redis Queue for audio processing
import redis
from rq import Queue

redis_conn = Redis(host='redis-cluster', port=6379)
queue = Queue('audio-processing', connection=redis_conn)

# User request → Queue → Available Worker → Process → Store results
# Workers can scale independently of API servers

# Target: 20 workers × (5-10 seconds per job) = 2-4 jobs/second
# Handle 10,000 users with queue depth ~100-200
```

**3. Database Scaling**:
```sql
-- PostgreSQL Read Replicas
-- 1 primary + 3 read replicas for analytics queries
-- Read scaling: 4x query capacity

-- MongoDB Sharding
-- Shard by user_id for chat data
-- 3 shard clusters for 10,000 users
```

**4. Caching Layer (Redis Cluster)**:
```python
# Cache frequently accessed data
CACHE_TTL = {
    'song_features': 86400,      # 24 hours
    'user_session': 3600,        # 1 hour
    'gentle_alignment': 604800,  # 1 week
}

# Cache hit rate target: >80%
# Reduces database load significantly
```

**5. CDN for Audio (CloudFront)**:
```python
# Reference audio cached at edge locations
# Popular songs: 80% cache hit rate
# Reduces S3 bandwidth costs
# Lower latency for users
```

#### Capacity Planning:

| Component | Quantity | Reasoning |
|-----------|----------|-----------|
| API Servers | 10 | 1,000 requests/instance |
| Workers | 20 | 5-10s processing time |
| Redis Nodes | 3 (cluster) | High availability |
| PostgreSQL | 1 primary + 3 replicas | Read scaling |
| MongoDB | 3 shards | Data distribution |
| S3 + CloudFront | 1 + edge | Audio delivery |

#### Auto-Scaling Rules:

```yaml
# Kubernetes HPA configuration
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: api-server-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: api-server
  minReplicas: 10
  maxReplicas: 50
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: 80

---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: worker-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: audio-worker
  minReplicas: 20
  maxReplicas: 100
  metrics:
    - type: External
      external:
        metric:
          name: queue_length
        target:
          type: AverageValue
          averageValue: "100"  # Add workers if queue > 100
```

---

### Q7: "What's your strategy for handling large audio files on S3? How do you optimize storage costs?"

**Current Implementation** (`s3_handler.py`):

```python
class StorageHandler:
    def __init__(self):
        self.is_production = os.getenv('PRODUCTION', 'false').lower() == 'true'
        self.bucket_name = os.getenv('S3_BUCKET_NAME', 'your-bucket-name')
        
        if self.is_production:
            self.s3_client = boto3.client('s3', 
                config=Config(signature_version='s3v4'),
                region_name=os.getenv("AWS_REGION"))
```

**Storage Optimization Strategies**:

#### 1. Lifecycle Policies (Automatic Tiering):

```json
{
  "Rules": [
    {
      "ID": "User Recordings Lifecycle",
      "Status": "Enabled",
      "Filter": {
        "Prefix": "user_recordings/"
      },
      "Transitions": [
        {
          "Days": 7,
          "StorageClass": "STANDARD_IA"  # Infrequent Access
        },
        {
          "Days": 30,
          "StorageClass": "GLACIER"  # Archive
        },
        {
          "Days": 90,
          "StorageClass": "DEEP_ARCHIVE"  # Deep Archive
        }
      ],
      "Expiration": {
        "Days": 365
      }
    },
    {
      "ID": "Analysis Results Lifecycle",
      "Status": "Enabled",
      "Filter": {
        "Prefix": "analysis_results/"
      },
      "Transitions": [
        {
          "Days": 30,
          "StorageClass": "GLACIER"
        }
      ],
      "Expiration": {
        "Days": 180
      }
    },
    {
      "ID": "Reference Audio Lifecycle",
      "Status": "Enabled",
      "Filter": {
        "Prefix": "songs/"
      },
      "Transitions": [
        {
          "Days": 90,
          "StorageClass": "STANDARD_IA"
        }
      ]
    }
  ]
}
```

#### 2. Storage Classes by Data Type:

| Data Type | Access Pattern | Storage Class | Cost (per GB/month) |
|-----------|----------------|---------------|---------------------|
| Active user recordings | High (practice) | Standard | $0.023 |
| Recent analyses (<30 days) | Medium | Standard-IA | $0.0125 |
| Old analyses (30-90 days) | Low | Glacier | $0.004 |
| Archive (>90 days) | Rare | Deep Archive | $0.00099 |
| Popular reference audio | High | Standard + CDN | $0.023 |
| Obscure reference audio | Low | Standard-IA | $0.0125 |
| Backups | Very rare | Glacier Deep Archive | $0.0004 |

#### 3. Intelligent-Tiering (Automatic Optimization):

```python
# Enable S3 Intelligent-Tiering for automatic cost optimization
# Moves data between access tiers based on usage patterns

# No retrieval fees for frequent access
# 0.015% monthly fee for auto-tiering
# Best for: Unknown or changing access patterns
```

#### 4. Audio Compression Strategy:

```python
import librosa
import soundfile as sf
import io

def compress_audio_for_storage(audio_path, target_bitrate=128000):
    """
    Compress audio using OPUS codec (better than MP3)
    - 50% smaller than MP3 at same quality
    - Better quality at same bitrate
    - Native web support
    """
    y, sr = librosa.load(audio_path, sr=16000)
    
    # Convert to OPUS
    buffer = io.BytesIO()
    sf.write(buffer, y, sr, format='OGG', subtype='OPUS')
    buffer.seek(0)
    
    # Upload compressed version
    s3_client.put_object(
        Bucket=bucket_name,
        Key=f"{path}.opus",
        Body=buffer.getvalue(),
        ContentType='audio/ogg'
    )
    
    return f"{path}.opus", buffer.tell()  # Return path and new size
```

#### 5. CloudFront CDN for Popular Content:

```python
# Configure CloudFront distribution for audio delivery
cloudfront = boto3.client('cloudfront')

# Cache popular reference audio at edge locations
# TTL: 1 year for reference audio (immutable)
# TTL: 1 hour for user recordings

# Benefits:
# - Lower latency for users (edge location near them)
# - Reduced S3 bandwidth costs (CloudFront cheaper)
# - Better user experience
```

#### 6. Cost Estimation:

**Current Monthly Cost (10,000 users × 10 recordings each × 5MB = 500GB)**:
```
All Standard: 500GB × $0.023 = $11.50/month
```

**Optimized Monthly Cost**:
```
User recordings:
  - 100GB Standard (active):     $2.30
  - 300GB Standard-IA (30d):     $3.75
  - 100GB Glacier (90d):         $0.40
                                ─────
  Subtotal:                      $6.45

Reference audio (1,000 songs × 10MB = 10GB):
  - 2GB Standard + CDN:          $0.046
  - 8GB Standard-IA:             $0.10
                                ─────
  Subtotal:                      $0.15

Analysis results (10GB):
  - 10GB Glacier:                $0.04

Total:                           $6.64/month
```

**Savings**: $11.50 - $6.64 = $4.86/month = **42% reduction**

#### 7. Monitoring and Alerts:

```python
# CloudWatch billing alerts
{
    "Threshold": 100,  # Alert at $100/month
    "ComparisonOperator": "GreaterThanThreshold",
    "EvaluationPeriods": 1,
    "AlarmName": "S3CostAlert",
    "MetricName": "EstimatedCharges",
    "Namespace": "AWS/Billing",
    "Period": 21600,  # 6 hours
    "Statistic": "Maximum"
}
```

**Key Optimization Summary**:
1. Lifecycle policies for automatic tiering
2. Intelligent-Tiering for unknown patterns
3. OPUS compression for smaller file sizes
4. CloudFront CDN for popular content
5. Monitoring and alerts for cost control
6. **Total estimated savings: 40-50%**

