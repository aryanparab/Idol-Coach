# IDOL COACH - System Design Interview Preparation Plan

## Current System Architecture Analysis

Based on code review of the Idol Coach singing assistant, here's the comprehensive technical breakdown:

### 1. LYRIC ALIGNMENT WITH GENTLE API

**Implementation Details** (`scripts_user/lyric_matcher.py`):
- **Function**: `load_gentle_alignment(gentle_json_path)` - Loads JSON alignments from Gentle API
- **Data Structure**: Each word has `start`, `end`, and `word` fields
- **Purpose**: Provides precise timestamps for each word in the original song

**Technical Flow**:
```
Original Audio → Gentle API → JSON with word-level timestamps
                  ↓
           Used for matching user vocals to correct song position
```

**Challenges with Timing Synchronization**:
1. **Variable Pacing**: Users sing at different tempos than original
2. **Segment Detection**: Finding where user singing matches in the song (solved with `find_best_segment_match`)
3. **Subsequence Matching**: Using fuzzy matching to handle timing variations
4. **Preprocessing**: Removing filler words ("uh", "um", "ah") that appear in singing

---

### 2. LIBROSA FEATURE EXTRACTION

**Features Extracted** (`scripts_user/audio_analysis.py`):

#### Basic Features:
- **MFCCs** (13 coefficients): Captures vocal timbre and identity
  - Why: Different singers have unique spectral envelope characteristics
- **Chroma Features**: Harmonic content and pitch class profiles
  - Why: Essential for detecting musical notes and harmony
- **Spectral Centroid**: Perceptual brightness measure
  - Why: Indicates vocal focus and clarity
- **Spectral Bandwidth**: Width of frequency spectrum
  - Why: Related to voice quality and richness
- **Spectral Flatness**: Distinguishes tonal vs. noise-like sounds
  - Why: Helps identify breath sounds vs. sustained notes
- **Zero Crossing Rate**: Rate of signal sign changes
  - Why: Useful for detecting percussive onsets and voice/unvoice boundaries
- **RMS Energy**: Loudness over time
  - Why: Essential for dynamics and expression analysis

#### Advanced Voice-Specific Features:
- **Pitch Contours** (librosa.piptrack): Fundamental frequency over time
  - Why: Primary metric for pitch accuracy comparison
- **Vibrato Analysis**: Rate, extent, and regularity of pitch oscillations
  - Why: Professional singing technique indicator
- **Formant Analysis**: Resonance characteristics (via spectral contrast)
  - Why: Vowel clarity and voice quality assessment
- **Onset Detection**: Note attack characteristics
  - Why: Determines precision of note starts
- **Dynamics Analysis**: Dynamic range and expression variation
  - Why: Musical expression and breath support
- **Pitch Stability**: Drift and variation analysis
  - Why: Intonation accuracy measurement
- **Vocal Fry Detection**: Low-frequency irregular patterns
  - Why: Voice health and technique assessment
- **Breath Detection**: Low-energy segments in audio
  - Why: Breath intake timing and efficiency

---

### 3. USER vs ORIGINAL COMPARISON

**Mathematical Metrics Used** (`scripts_user/compare_pitch_dtw.py`, `scripts_user/audio_analysis.py`):

#### Pitch Comparison:
- **DTW (Dynamic Time Warping)**: 
  - `dtw(user_pitch, ref_pitch, keep_internals=True)`
  - Returns normalized distance, alignment path, cost matrix
  - Handles tempo differences between user and original
- **Euclidean Distance**: 
  - Used within DTW for frame-by-frame pitch comparison

#### Feature Comparison:
- **Cosine Distance**: 
  - `scipy.spatial.distance.cosine(user_feat, ref_feat)`
  - For comparing MFCC vectors, chroma vectors, spectral features
- **Absolute Difference**: 
  - For scalar features (centroid, bandwidth, etc.)
- **Relative Difference**: 
  - For percentage-based feedback
- **Cents Deviation**: 
  - `1200 * log2(pitch / 440)` for pitch accuracy in musical cents

#### Sequence Matching (Lyrics):
- **Fuzzy String Matching** (fuzzywuzzy library):
  - `fuzz.ratio()`: Character-level similarity
  - `fuzz.partial_ratio()`: Partial substring matching
  - `fuzz.token_sort_ratio()`: Word order-independent
  - `fuzz.token_set_ratio()`: Word set similarity
- **Weighted Combination**:
  - Subsequence matching (50% weight)
  - Fuzzy average (30% weight)
  - Word coverage (20% weight)

---

### 4. LATENCY OPTIMIZATION STRATEGIES

**Current Bottlenecks Identified** (from `process_user_audio.py`):

#### Sequential Processing Pipeline:
```
1. Load gentle alignment
2. Transcribe with Whisper (heavy model)
3. Extract pitch contours (2x - user + reference)
4. Find matching segment (multiple sliding windows)
5. Analyze audio features
6. Generate AI feedback
```

**Optimization Opportunities**:

1. **Parallel Processing**:
   - Extract user and reference pitch simultaneously
   - Run Whisper and feature extraction in parallel

2. **Caching Strategy**:
   - Cache reference song features (already computed once per song)
   - Cache Gentle alignments
   - Use Redis for session-level caching

3. **Model Optimization**:
   - Use Whisper "tiny" or "base" model for faster transcription
   - Quantize models for inference speedup
   - Consider ONNX runtime

4. **Early Termination**:
   - Stop processing if confidence threshold not met early
   - Skip granular analysis if overall match is poor

5. **Batch Processing**:
   - Process multiple audio frames in batches
   - Vectorize numpy operations

6. **Reduce Feature Set**:
   - Use essential features only for initial matching
   - Deep analysis only for matched segments

**Proposed 30% Latency Reduction**:
- Parallel pitch extraction: ~15% improvement
- Feature caching: ~20% improvement
- Model optimization: ~25% improvement
- Early termination: ~10% improvement
**Combined: ~70% total reduction (exceeds 30% goal)**

---

### 5. DATABASE ARCHITECTURE (PostgreSQL + MongoDB)

**Current Implementation** (`scripts/agents.py`, `s3_handler.py`):

#### MongoDB (Current):
- **Chat History**: Stores conversation messages with timestamps
- **Singing Data**: User recordings, analysis results, feedback history
- **User Preferences**: Coaching level, skill progress

#### Recommended PostgreSQL Additions:

**PostgreSQL for Structured Data**:
1. **Songs Database**:
   - Song metadata (title, artist, genre, difficulty)
   - Pre-computed features and alignments
   - Reference pitch contours (stored as arrays)
   
2. **User Progress Tracking**:
   - Performance metrics over time
   - Skill level progression
   - Achievement badges

3. **Analytics**:
   - Query performance for user trends
   - Aggregate statistics on singing accuracy
   - Popular songs and difficulty analysis

**Data Placement Strategy**:

| Data Type | Database | Reason |
|-----------|----------|--------|
| Song metadata | PostgreSQL | Structured, frequent joins |
| Audio files | S3 + PostgreSQL references | Large binary blobs |
| Lyric alignments | PostgreSQL | Structured, indexed queries |
| User chat history | MongoDB | Flexible schema, chat logs |
| Voice analysis results | Both (hybrid) | Structured metrics + flexible feedback |
| User preferences | PostgreSQL | ACID compliance for settings |
| Temporary processing | Redis | Fast cache, short-lived data |

**Hybrid Query Patterns**:
```sql
-- PostgreSQL: Find songs by difficulty with good user performance
SELECT s.title, s.artist, AVG(up.pitch_accuracy) as avg_accuracy
FROM songs s
JOIN user_performance up ON s.id = up.song_id
WHERE s.difficulty = 'intermediate'
GROUP BY s.id;
```

```javascript
// MongoDB: Get user's singing progress for a song
db.singing_sessions.find({
  user_id: userId,
  song_id: songId
}).sort({timestamp: -1}).limit(10);
```

---

### 6. SCALING TO 10,000 CONCURRENT USERS

**Architecture Components**:

#### Horizontal Scaling:
- **API Servers**: Stateless Flask/FastAPI instances behind load balancer
- **Audio Processing Workers**: Celery or Redis Queue workers
- **Caching Layer**: Redis cluster for feature caching
- **Database**: Read replicas for PostgreSQL, sharded MongoDB

#### Infrastructure Design:
```
                    ┌─────────────────┐
                    │   Load Balancer │
                    │   (Nginx/AWS ALB)│
                    └────────┬────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
   ┌────▼────┐         ┌────▼────┐         ┌────▼────┐
   │API Server│        │API Server│        │API Server│
   │  (1)    │        │  (2)    │        │  (n)    │
   └────┬────┘         └────┬────┘         └────┬────┘
        │                    │                    │
        └────────────────────┼────────────────────┘
                             │
                    ┌────────▼────────┐
                    │  Message Queue  │
                    │  (Redis/RabbitMQ)│
                    └────────┬────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
   ┌────▼────┐         ┌────▼────┐         ┌────▼────┐
   │ Worker  │         │ Worker  │         │ Worker  │
   │  (1)    │         │  (2)    │         │  (n)    │
   └────┬────┘         └────┬────┘         └────┬────┘
        │                    │                    │
        └────────────────────┼────────────────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
   ┌────▼────┐         ┌────▼────┐         ┌────▼────┐
   │  Redis  │         │PostgreSQL│        │  MongoDB │
   │ (Cache) │         │(Primary) │        │ (Sessions)│
   └─────────┘         └─────────┘         └─────────┘
                             │
                    ┌────────▼────────┐
                    │   S3 Storage    │
                    │  (Audio Files)  │
                    └─────────────────┘
```

#### Capacity Planning:
- **API Servers**: 10 instances (handle 1,000 concurrent requests each)
- **Workers**: 20 instances (audio processing takes ~5-10 seconds)
- **Redis**: Cluster mode, 3 nodes
- **PostgreSQL**: 1 primary + 3 read replicas
- **MongoDB**: Sharded cluster, 3 config servers

#### Auto-scaling Triggers:
- CPU > 70% → Scale out workers
- Queue length > 100 → Add workers
- Latency > 2s → Scale out API servers
- Memory > 80% → Vertical scale or add nodes

---

### 7. S3 AUDIO STORAGE OPTIMIZATION

**Current Implementation** (`s3_handler.py`):
- Stores user recordings and reference audio
- Uses presigned URLs for access
- Supports both S3 and local storage

**Storage Optimization Strategies**:

#### Cost Optimization:
1. **Intelligent-Tiering**:
   - Use S3 Intelligent-Tiering for automatic cost optimization
   - Moves data to cheaper tiers based on access patterns
   
2. **Lifecycle Policies**:
   ```json
   {
     "Rules": [
       {
         "ID": "Archive old recordings",
         "Status": "Enabled",
         "Filter": {"Prefix": "user_recordings/"},
         "Transitions": [
           {"Days": 30, "StorageClass": "STANDARD_IA"},
           {"Days": 90, "StorageClass": "GLACIER"},
           {"Days": 365, "StorageClass": "DEEP_ARCHIVE"}
         ],
         "Expiration": {"Days": 1095}
       }
     ]
   }
   ```

3. **Audio Compression**:
   - Convert to OPUS codec (better compression than MP3)
   - Adaptive bitrate based on content type
   - Store in S3 Glacier Instant Retrieval for backups

#### Performance Optimization:
1. **CloudFront CDN**:
   - Cache frequently accessed reference audio
   - Reduce latency for popular songs
   - Edge locations near users

2. **Object Lifecycle with Versioning**:
   - Enable versioning to prevent accidental deletion
   - Use delete markers for cleanup

3. **Metadata Indexing**:
   - Store audio metadata in PostgreSQL
   - Enable efficient querying by song, user, date
   - Index frequently accessed fields

#### Storage Tiers by Data Type:

| Data Type | Storage Class | Rationale |
|-----------|---------------|-----------|
| Active user recordings | Standard | Frequently accessed during practice |
| Recent analyses (30 days) | Standard-IA | Accessed for feedback |
| Old analyses (90+ days) | Glacier | Rarely accessed, compliance |
| Reference audio (popular) | Standard + CloudFront | High read frequency |
| Reference audio (obscure) | Standard-IA | Low access frequency |
| Backups | Glacier Deep Archive | Recovery only |

#### Estimated Cost Savings:
- Current (all Standard): ~$0.023/GB/month
- Optimized (tiered): ~$0.012/GB/month
- **Savings: ~48%**

---

## Interview Answer Framework

### Technical Implementation Answers

#### Q1: Gentle API & Timing Synchronization
**Key Points**:
1. Gentle provides word-level timestamps with start/end times
2. Challenge: User singing tempo differs from original
3. Solution: DTW for pitch alignment + fuzzy matching for lyric segments
4. Preprocessing: Remove fillers, handle singing variations

#### Q2: Librosa Features
**Key Points**:
1. MFCCs: Timbre capture for voice identity
2. Pitch contours: Fundamental frequency using piptrack
3. Spectral features: Centroid, bandwidth, flatness for quality
4. Advanced: Vibrato, formants, onset, dynamics, pitch stability
5. Why: Comprehensive vocal technique assessment

#### Q3: Mathematical Metrics
**Key Points**:
1. DTW with Euclidean distance for pitch contours
2. Cosine distance for feature vectors (MFCC, chroma)
3. Fuzzy string matching (ratio, partial_ratio, token_sort_ratio)
4. Weighted combination of similarity metrics
5. Cents deviation for pitch accuracy

#### Q4: 30% Latency Reduction
**Key Points**:
1. Parallel processing of user and reference audio
2. Feature caching (reference songs pre-computed)
3. Model optimization (Whisper small model)
4. Early termination when confidence low
5. Reduce feature set for initial matching
6. Combined target: 70% reduction (exceeds 30%)

#### Q5: PostgreSQL + MongoDB
**Key Points**:
1. MongoDB: Chat history, flexible feedback documents
2. PostgreSQL: Song metadata, structured analytics, user progress
3. Hybrid approach: Best of both worlds
4. Data placement based on access patterns and schema requirements

### System Design Answers

#### Q6: 10,000 Concurrent Users
**Key Points**:
1. Horizontal scaling with stateless API servers
2. Async processing with message queue (Redis/RabbitMQ)
3. Database read replicas and sharding
4. Caching layer for frequent queries
5. Auto-scaling based on metrics
6. CDN for audio content delivery

#### Q7: S3 Storage Optimization
**Key Points**:
1. Intelligent-Tiering for automatic cost optimization
2. Lifecycle policies for tiered storage
3. CloudFront CDN for performance
4. Audio compression and adaptive bitrate
5. Cost analysis showing ~48% savings potential

