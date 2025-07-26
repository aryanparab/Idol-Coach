import numpy as np
import librosa
from scipy.spatial.distance import cosine
from scipy import signal
from scipy.ndimage import gaussian_filter1d
import json
from scripts_user.compare_pitch_dtw import segment_pitch_contour, compare_with_dtw, extract_pitch_contour
import os 
from s3_handler import storage
import tempfile

class ComprehensiveVocalAnalyzer:
    """
    Complete vocal analysis system combining overall and granular feedback
    """
    
    def __init__(self, sr=16000, hop_length=512):
        self.sr = sr
        self.hop_length = hop_length
    
    def load_audio_from_storage(self,audio_path, sr):
            if storage.is_production and storage.file_exists(audio_path):
                # For S3, download to temporary file first
                with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                    audio_data = storage.read_file(audio_path, mode='rb')
                    temp_file.write(audio_data)
                    temp_file.flush()
                    
                    # Load audio from temporary file
                    y, loaded_sr = librosa.load(temp_file.name, sr=sr)
                    
                    # Clean up temporary file
                    os.unlink(temp_file.name)
                    return y, loaded_sr
            else:
                # For local storage
                return librosa.load(audio_path, sr=sr)
    def segment_audio(self, audio_path, start_time, end_time):
        """Segment audio file between timestamps"""
        y, _ = self.load_audio_from_storage(audio_path, sr=self.sr)
        start_sample = int(start_time * self.sr)
        end_sample = int(end_time * self.sr)
        return y[start_sample:end_sample], self.sr
    
    def to_serializable(self, obj):
        """Convert numpy objects to JSON serializable format"""
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, (np.float32, np.float64)):
            return float(obj)
        if isinstance(obj, (np.int32, np.int64)):
            return int(obj)
        return obj
    
    # ================ BREATH ANALYSIS ================
    def detect_breath_segments(self, y):
        """Detect potential breath intake locations"""
        rms = librosa.feature.rms(y=y, frame_length=2048, hop_length=self.hop_length)[0]
        rms_smooth = gaussian_filter1d(rms, sigma=2)
        
        # Find low energy segments that could be breaths
        threshold = np.mean(rms_smooth) * 0.3  # Adaptive threshold
        breath_candidates = rms_smooth < threshold
        breath_segments = []
        
        in_breath = False
        start_frame = 0
        
        for i, is_breath in enumerate(breath_candidates):
            if is_breath and not in_breath:
                start_frame = i
                in_breath = True
            elif not is_breath and in_breath:
                if i - start_frame > 5:  # Minimum breath duration
                    breath_segments.append({
                        'start_time': start_frame * self.hop_length / self.sr,
                        'end_time': i * self.hop_length / self.sr,
                        'duration': (i - start_frame) * self.hop_length / self.sr
                    })
                in_breath = False
        
        return breath_segments
    
    # ================ VIBRATO ANALYSIS ================
    def analyze_vibrato(self, pitch_contour):
        """Analyze vibrato characteristics"""
        if pitch_contour is None or len(pitch_contour) < 20:
            return {'vibrato_rate': 0, 'vibrato_extent': 0, 'vibrato_regularity': 0}
        
        # Remove zeros and interpolate
        valid_pitch = pitch_contour[pitch_contour > 0]
        if len(valid_pitch) < 20:
            return {'vibrato_rate': 0, 'vibrato_extent': 0, 'vibrato_regularity': 0}
        
        # Smooth the pitch to remove noise
        smoothed_pitch = gaussian_filter1d(valid_pitch, sigma=2)
        
        # Calculate vibrato rate (oscillations per second)
        time_per_frame = self.hop_length / self.sr
        peaks, _ = signal.find_peaks(smoothed_pitch, distance=5)
        vibrato_rate = len(peaks) / (len(smoothed_pitch) * time_per_frame) if len(peaks) > 0 else 0
        
        # Calculate vibrato extent (pitch variation)
        if len(smoothed_pitch) > 10:
            pitch_std = np.std(smoothed_pitch)
            vibrato_extent = pitch_std / np.mean(smoothed_pitch) if np.mean(smoothed_pitch) > 0 else 0
        else:
            vibrato_extent = 0
        
        # Vibrato regularity (consistency of oscillations)
        if len(peaks) > 2:
            peak_intervals = np.diff(peaks)
            vibrato_regularity = 1 - (np.std(peak_intervals) / np.mean(peak_intervals)) if np.mean(peak_intervals) > 0 else 0
            vibrato_regularity = max(0, vibrato_regularity)
        else:
            vibrato_regularity = 0
        
        return {
            'vibrato_rate': vibrato_rate,
            'vibrato_extent': vibrato_extent,
            'vibrato_regularity': vibrato_regularity
        }
    
    # ================ FORMANT ANALYSIS ================
    def analyze_formants(self, y):
        """Extract formant information for vowel analysis"""
        # Pre-emphasis filter
        pre_emphasized = signal.lfilter([1, -0.97], [1], y)
        
        # Get spectral features that correlate with formants
        spectral_contrast = librosa.feature.spectral_contrast(y=pre_emphasized, sr=self.sr, n_bands=6)
        
        return {
            'formant_clarity': np.mean(np.std(spectral_contrast, axis=1)),
            'vowel_definition': np.mean(spectral_contrast),
            'spectral_contrast_mean': np.mean(spectral_contrast, axis=1),
            'spectral_contrast_std': np.std(spectral_contrast, axis=1)
        }
    
    # ================ ONSET ANALYSIS ================
    def analyze_onset_quality(self, y):
        """Analyze note onset characteristics"""
        onset_frames = librosa.onset.onset_detect(y=y, sr=self.sr, units='frames')
        onset_strength = librosa.onset.onset_strength(y=y, sr=self.sr)
        
        if len(onset_frames) == 0:
            return {'onset_sharpness': 0, 'onset_consistency': 0, 'attack_time': 0}
        
        # Calculate onset sharpness (how quickly notes start)
        onset_sharpness = np.mean([onset_strength[frame] for frame in onset_frames])
        
        # Onset consistency
        onset_strengths = [onset_strength[frame] for frame in onset_frames]
        onset_consistency = 1 - (np.std(onset_strengths) / np.mean(onset_strengths)) if np.mean(onset_strengths) > 0 else 0
        
        # Average attack time (rise time to peak)
        rms = librosa.feature.rms(y=y)[0]
        peak_rms = np.max(rms)
        attack_frames = np.where(rms > peak_rms * 0.9)[0]
        attack_time = len(attack_frames) * self.hop_length / self.sr if len(attack_frames) > 0 else 0
        
        return {
            'onset_sharpness': onset_sharpness,
            'onset_consistency': max(0, onset_consistency),
            'attack_time': attack_time
        }
    
    # ================ DYNAMICS ANALYSIS ================
    def analyze_dynamics_expression(self, y):
        """Analyze dynamic range and expression"""
        rms = librosa.feature.rms(y=y, frame_length=2048, hop_length=self.hop_length)[0]
        
        # Dynamic range
        dynamic_range = np.max(rms) - np.min(rms) if len(rms) > 0 else 0
        
        # Expression variation (how much the dynamics change)
        rms_smooth = gaussian_filter1d(rms, sigma=3)
        expression_variation = np.std(rms_smooth)
        
        # Sustain quality (consistency during held notes)
        sustain_stability = 1 - (np.std(rms) / np.mean(rms)) if np.mean(rms) > 0 else 0
        sustain_stability = max(0, sustain_stability)
        
        return {
            'dynamic_range': dynamic_range,
            'expression_variation': expression_variation,
            'sustain_stability': sustain_stability,
            'average_energy': np.mean(rms)
        }
    
    # ================ PITCH STABILITY ANALYSIS ================
    def analyze_pitch_stability(self, pitch_contour):
        """Analyze pitch drift and stability"""
        if pitch_contour is None or len(pitch_contour) < 10:
            return {'pitch_drift': 0, 'pitch_stability': 0, 'intonation_accuracy': 0}
        
        valid_pitch = pitch_contour[pitch_contour > 0]
        if len(valid_pitch) < 10:
            return {'pitch_drift': 0, 'pitch_stability': 0, 'intonation_accuracy': 0}
        
        # Pitch drift (gradual change over time)
        time_points = np.arange(len(valid_pitch))
        if len(time_points) > 1:
            drift_slope = np.polyfit(time_points, valid_pitch, 1)[0]
            pitch_drift = abs(drift_slope)
        else:
            pitch_drift = 0
        
        # Pitch stability (variation around the mean)
        pitch_stability = 1 - (np.std(valid_pitch) / np.mean(valid_pitch)) if np.mean(valid_pitch) > 0 else 0
        pitch_stability = max(0, pitch_stability)
        
        # Intonation accuracy (how close to semitone centers)
        cents_from_semitones = []
        for pitch in valid_pitch:
            if pitch > 0:
                cents = 1200 * np.log2(pitch / 440)  # Convert to cents from A4
                nearest_semitone = round(cents / 100) * 100
                cents_from_semitones.append(abs(cents - nearest_semitone))
        
        intonation_accuracy = 1 - (np.mean(cents_from_semitones) / 50) if cents_from_semitones else 0
        intonation_accuracy = max(0, intonation_accuracy)
        
        return {
            'pitch_drift': pitch_drift,
            'pitch_stability': pitch_stability,
            'intonation_accuracy': intonation_accuracy
        }
    
    # ================ VOICE QUALITY ANALYSIS ================
    def detect_vocal_fry(self, y):
        """Detect vocal fry (creaky voice)"""
        # Analyze low-frequency energy and irregularity
        f0, voiced_flag, voiced_probs = librosa.pyin(y, fmin=50, fmax=300, sr=self.sr)
        
        # Look for irregular pitch patterns typical of vocal fry
        if np.sum(voiced_flag) < 5:
            return {'vocal_fry_amount': 0, 'voice_quality': 1.0}
        
        valid_f0 = f0[voiced_flag]
        
        # Vocal fry typically shows as very low pitch with high irregularity
        low_pitch_frames = np.sum(valid_f0 < 100) / len(valid_f0) if len(valid_f0) > 0 else 0
        
        # Irregularity in pitch
        pitch_irregularity = np.std(np.diff(valid_f0)) / np.mean(valid_f0) if len(valid_f0) > 1 and np.mean(valid_f0) > 0 else 0
        
        vocal_fry_amount = min(1.0, low_pitch_frames * pitch_irregularity * 10)
        voice_quality = 1.0 - vocal_fry_amount
        
        return {
            'vocal_fry_amount': vocal_fry_amount,
            'voice_quality': voice_quality
        }
    
    # ================ COMPREHENSIVE FEATURE EXTRACTION ================
    def extract_comprehensive_features(self, y):
        """Extract all features including original and enhanced ones"""
        features = {}
        
        # ============ ORIGINAL FEATURES ============
        mfcc = librosa.feature.mfcc(y=y, sr=self.sr, n_mfcc=13)
        features["mfcc_mean"] = np.mean(mfcc, axis=1)
        features["mfcc_std"] = np.std(mfcc, axis=1)

        chroma = librosa.feature.chroma_stft(y=y, sr=self.sr)
        features["chroma_mean"] = np.mean(chroma, axis=1)
        features["chroma_std"] = np.std(chroma, axis=1)

        features["spectral_centroid"] = np.mean(librosa.feature.spectral_centroid(y=y, sr=self.sr))
        features["spectral_bandwidth"] = np.mean(librosa.feature.spectral_bandwidth(y=y, sr=self.sr))
        features["spectral_flatness"] = np.mean(librosa.feature.spectral_flatness(y=y))

        features["zcr"] = np.mean(librosa.feature.zero_crossing_rate(y))
        features["rms"] = np.mean(librosa.feature.rms(y=y))
        
        # ============ ENHANCED FEATURES ============
        
        # Breath analysis
        breath_segments = self.detect_breath_segments(y)
        features["breath_count"] = len(breath_segments)
        features["average_breath_duration"] = np.mean([b['duration'] for b in breath_segments]) if breath_segments else 0
        
        # Extract pitch contour
        f0, voiced_flag, voiced_probs = librosa.pyin(y, fmin=80, fmax=800, sr=self.sr)
        
        # Vibrato analysis
        vibrato_features = self.analyze_vibrato(f0)
        features.update(vibrato_features)
        
        # Formant analysis
        formant_features = self.analyze_formants(y)
        features.update(formant_features)
        
        # Onset quality
        onset_features = self.analyze_onset_quality(y)
        features.update(onset_features)
        
        # Dynamics and expression
        dynamics_features = self.analyze_dynamics_expression(y)
        features.update(dynamics_features)
        
        # Pitch stability
        pitch_stability_features = self.analyze_pitch_stability(f0)
        features.update(pitch_stability_features)
        
        # Vocal quality
        vocal_quality_features = self.detect_vocal_fry(y)
        features.update(vocal_quality_features)
        
        return features
    
    # ================ FRAME-LEVEL FEATURES FOR GRANULAR ANALYSIS ================
    def extract_frame_level_features(self, y):
        """Extract features at frame level for granular analysis"""
        frames = {}
        
        # Frame-level pitch
        f0, voiced_flag, voiced_probs = librosa.pyin(y, fmin=80, fmax=800, sr=self.sr, hop_length=self.hop_length)
        frames['pitch'] = f0
        frames['voiced_confidence'] = voiced_probs
        
        # Frame-level energy
        rms = librosa.feature.rms(y=y, hop_length=self.hop_length)[0]
        frames['energy'] = rms
        
        # Frame-level spectral features
        spectral_centroid = librosa.feature.spectral_centroid(y=y, sr=self.sr, hop_length=self.hop_length)[0]
        spectral_bandwidth = librosa.feature.spectral_bandwidth(y=y, sr=self.sr, hop_length=self.hop_length)[0]
        spectral_flatness = librosa.feature.spectral_flatness(y=y, hop_length=self.hop_length)[0]
        
        frames['spectral_centroid'] = spectral_centroid
        frames['spectral_bandwidth'] = spectral_bandwidth
        frames['spectral_flatness'] = spectral_flatness
        
        # Frame-level MFCC for timbre
        mfcc = librosa.feature.mfcc(y=y, sr=self.sr, n_mfcc=13, hop_length=self.hop_length)
        frames['mfcc'] = mfcc
        
        # Frame-level chroma for harmony
        chroma = librosa.feature.chroma_stft(y=y, sr=self.sr, hop_length=self.hop_length)
        frames['chroma'] = chroma
        
        # Convert frame indices to time
        frame_times = librosa.frames_to_time(np.arange(len(frames['pitch'])), sr=self.sr, hop_length=self.hop_length)
        frames['frame_times'] = frame_times
        
        return frames
    
    # ================ FEATURE COMPARISON ================
    def compare_comprehensive_features(self, user_feat, ref_feat):
        """Compare feature sets with enhanced metrics"""
        comparison = {}
        
        for key in user_feat:
            if key not in ref_feat:
                continue
                
            if isinstance(user_feat[key], np.ndarray):
                if len(user_feat[key]) == len(ref_feat[key]):
                    comparison[key + "_cosine_difference"] = cosine(user_feat[key], ref_feat[key])
                else:
                    # Handle different array lengths
                    min_len = min(len(user_feat[key]), len(ref_feat[key]))
                    comparison[key + "_cosine_difference"] = cosine(
                        user_feat[key][:min_len], 
                        ref_feat[key][:min_len]
                    )
            else:
                comparison[key + "_abs_diff"] = abs(user_feat[key] - ref_feat[key])
                # Add relative difference for percentage-based feedback
                if ref_feat[key] != 0:
                    comparison[key + "_relative_diff"] = (user_feat[key] - ref_feat[key]) / ref_feat[key]
                else:
                    comparison[key + "_relative_diff"] = 0
        
        return comparison
    
    # ================ GRANULAR ANALYSIS ================
    def align_words_to_timestamps(self, lyrics_words, start_time, end_time):
        """Distribute words evenly across the time segment"""
        if not lyrics_words:
            return []
        
        duration = end_time - start_time
        time_per_word = duration / len(lyrics_words)
        
        word_timestamps = []
        for i, word in enumerate(lyrics_words):
            word_start = start_time + (i * time_per_word)
            word_end = start_time + ((i + 1) * time_per_word)
            word_timestamps.append({
                'word': word,
                'start_time': word_start,
                'end_time': word_end,
                'position': i
            })
        
        return word_timestamps
    
    def analyze_word_level_performance(self, user_frames, ref_frames, word_timestamp, tolerance_cents=50):
        """Analyze performance for a specific word/timestamp"""
        
        # Find frames that correspond to this word
        word_start = word_timestamp['start_time']
        word_end = word_timestamp['end_time']
        
        # Get user frames for this word
        user_mask = (user_frames['frame_times'] >= word_start) & (user_frames['frame_times'] <= word_end)
        ref_mask = (ref_frames['frame_times'] >= 0) & (ref_frames['frame_times'] <= (word_end - word_start))
        
        if not np.any(user_mask) or not np.any(ref_mask):
            return None
        
        analysis = {
            'word': word_timestamp['word'],
            'timestamp': f"{word_start:.2f}-{word_end:.2f}s",
            'issues': [],
            'strengths': [],
            'specific_recommendations': []
        }
        
        # Pitch analysis
        user_pitch = user_frames['pitch'][user_mask]
        ref_pitch = ref_frames['pitch'][ref_mask]
        
        user_pitch_clean = user_pitch[~np.isnan(user_pitch) & (user_pitch > 0)]
        ref_pitch_clean = ref_pitch[~np.isnan(ref_pitch) & (ref_pitch > 0)]
        
        if len(user_pitch_clean) > 0 and len(ref_pitch_clean) > 0:
            # Convert to cents for comparison
            user_cents = 1200 * np.log2(user_pitch_clean / 440)
            ref_cents = 1200 * np.log2(ref_pitch_clean / 440)
            
            pitch_diff = np.mean(user_cents) - np.mean(ref_cents)
            pitch_stability = np.std(user_cents)
            ref_stability = np.std(ref_cents)
            
            if abs(pitch_diff) > tolerance_cents:
                direction = "sharp" if pitch_diff > 0 else "flat"
                cents_off = abs(pitch_diff)
                analysis['issues'].append({
                    'type': 'pitch_accuracy',
                    'severity': 'high' if cents_off > 100 else 'medium',
                    'description': f"Pitch is {cents_off:.0f} cents {direction}",
                    'reference_pitch': f"{np.mean(ref_cents):.0f} cents",
                    'user_pitch': f"{np.mean(user_cents):.0f} cents"
                })
                analysis['specific_recommendations'].append(
                    f"The word '{word_timestamp['word']}' should be sung {cents_off:.0f} cents {'lower' if direction == 'sharp' else 'higher'}. "
                    f"Try imagining the pitch {'dropping' if direction == 'sharp' else 'lifting'} slightly on this word."
                )
            else:
                analysis['strengths'].append(f"Excellent pitch accuracy on '{word_timestamp['word']}'")
            
            # Pitch stability comparison
            if pitch_stability > ref_stability * 1.5:
                analysis['issues'].append({
                    'type': 'pitch_stability',
                    'severity': 'medium',
                    'description': f"Pitch wavers too much (std: {pitch_stability:.1f} vs reference: {ref_stability:.1f})",
                    'user_stability': pitch_stability,
                    'ref_stability': ref_stability
                })
                analysis['specific_recommendations'].append(
                    f"On '{word_timestamp['word']}', focus on steady breath support to reduce pitch wavering. "
                    f"The original has more stable pitch here."
                )
        
        # Energy/dynamics analysis
        user_energy = np.mean(user_frames['energy'][user_mask])
        ref_energy = np.mean(ref_frames['energy'][ref_mask])
        
        energy_ratio = user_energy / ref_energy if ref_energy > 0 else 1
        
        if energy_ratio < 0.7:
            analysis['issues'].append({
                'type': 'energy_low',
                'severity': 'medium',
                'description': f"Energy is {(1-energy_ratio)*100:.0f}% lower than reference",
                'user_energy': user_energy,
                'ref_energy': ref_energy
            })
            analysis['specific_recommendations'].append(
                f"'{word_timestamp['word']}' needs more vocal energy and projection. "
                f"The original singer uses {(1/energy_ratio)*100:.0f}% more power here."
            )
        elif energy_ratio > 1.3:
            analysis['issues'].append({
                'type': 'energy_high',
                'severity': 'low',
                'description': f"Energy is {(energy_ratio-1)*100:.0f}% higher than reference",
                'user_energy': user_energy,
                'ref_energy': ref_energy
            })
            analysis['specific_recommendations'].append(
                f"'{word_timestamp['word']}' could be sung with less force. "
                f"Try a more relaxed approach like in the original."
            )
        
        # Timbre analysis (spectral characteristics)
        user_centroid = np.mean(user_frames['spectral_centroid'][user_mask])
        ref_centroid = np.mean(ref_frames['spectral_centroid'][ref_mask])
        
        centroid_diff = (user_centroid - ref_centroid) / ref_centroid if ref_centroid > 0 else 0
        
        if abs(centroid_diff) > 0.2:  # 20% difference
            tone_direction = "brighter" if centroid_diff > 0 else "darker"
            opposite_direction = "darker" if centroid_diff > 0 else "brighter"
            
            analysis['issues'].append({
                'type': 'timbre_mismatch',
                'severity': 'medium',
                'description': f"Tone is {abs(centroid_diff)*100:.0f}% {tone_direction} than reference",
                'user_centroid': user_centroid,
                'ref_centroid': ref_centroid
            })
            analysis['specific_recommendations'].append(
                f"On '{word_timestamp['word']}', try a {opposite_direction} tone quality. "
                f"The original has a {'warmer' if opposite_direction == 'darker' else 'clearer'} sound here."
            )
        
        # Vowel quality analysis using chroma/formant proxy
        if np.any(user_mask) and np.any(ref_mask):
            user_chroma = np.mean(user_frames['chroma'][:, user_mask], axis=1)
            ref_chroma = np.mean(ref_frames['chroma'][:, ref_mask], axis=1)
            
            if len(user_chroma) == len(ref_chroma):
                chroma_similarity = 1 - cosine(user_chroma, ref_chroma)
                
                if chroma_similarity < 0.8:  # Low similarity threshold
                    analysis['issues'].append({
                        'type': 'vowel_clarity',
                        'severity': 'medium',
                        'description': f"Vowel formation differs from reference (similarity: {chroma_similarity:.2f})",
                        'chroma_similarity': chroma_similarity
                    })
                    analysis['specific_recommendations'].append(
                        f"Focus on clearer vowel formation on '{word_timestamp['word']}'. "
                        f"Listen to how the original singer shapes this vowel."
                    )
        
        return analysis
    
    def generate_granular_feedback(self, word_analyses):
        """Generate human-readable granular feedback"""
        
        if not word_analyses:
            return {"summary": "No specific analysis available", "detailed_feedback": []}
        
        # Filter out None analyses
        valid_analyses = [a for a in word_analyses if a is not None]
        
        if not valid_analyses:
            return {"summary": "Insufficient audio data for granular analysis", "detailed_feedback": []}
        
        # Categorize issues by severity and type
        high_priority_issues = []
        medium_priority_issues = []
        strengths = []
        
        detailed_feedback = []
        
        for analysis in valid_analyses:
            word_feedback = {
                'word': analysis['word'],
                'timestamp': analysis['timestamp'],
                'feedback': []
            }
            
            # Add issues
            for issue in analysis['issues']:
                feedback_text = ""
                if issue['type'] == 'pitch_accuracy':
                    feedback_text = f"🎵 Pitch issue: {issue['description']}"
                    if issue['severity'] == 'high':
                        high_priority_issues.append(f"{analysis['word']} at {analysis['timestamp']}")
                    else:
                        medium_priority_issues.append(f"{analysis['word']} at {analysis['timestamp']}")
                
                elif issue['type'] == 'energy_low':
                    feedback_text = f"⚡ Energy: {issue['description']}"
                    medium_priority_issues.append(f"{analysis['word']} at {analysis['timestamp']}")
                
                elif issue['type'] == 'timbre_mismatch':
                    feedback_text = f"🎨 Tone: {issue['description']}"
                    medium_priority_issues.append(f"{analysis['word']} at {analysis['timestamp']}")
                
                elif issue['type'] == 'vowel_clarity':
                    feedback_text = f"🗣️ Vowel: {issue['description']}"
                    medium_priority_issues.append(f"{analysis['word']} at {analysis['timestamp']}")
                
                if feedback_text:
                    word_feedback['feedback'].append(feedback_text)
            
            # Add recommendations
            for rec in analysis['specific_recommendations']:
                word_feedback['feedback'].append(f"💡 {rec}")
            
            # Add strengths
            for strength in analysis['strengths']:
                word_feedback['feedback'].append(f"✅ {strength}")
                strengths.append(f"{analysis['word']} at {analysis['timestamp']}")
            
            if word_feedback['feedback']:
                detailed_feedback.append(word_feedback)
        
        # Generate summary
        summary_parts = []
        if high_priority_issues:
            summary_parts.append(f"🚨 Priority fixes needed: {', '.join(high_priority_issues[:3])}")
        if medium_priority_issues:
            summary_parts.append(f"🔧 Areas to improve: {', '.join(medium_priority_issues[:3])}")
        if strengths:
            summary_parts.append(f"✨ Great work on: {', '.join(strengths[:3])}")
        
        summary = " | ".join(summary_parts) if summary_parts else "Analysis complete"
        
        return {
            "summary": summary,
            "detailed_feedback": detailed_feedback,
            "stats": {
                "high_priority_issues": len(high_priority_issues),
                "medium_priority_issues": len(medium_priority_issues),
                "strengths": len(strengths),
                "words_analyzed": len(valid_analyses)
            }
        }
    



def analyze_audio_match_enhanced(user_audio_path, reference_audio_path, match, ref_pitch, 
                               coaching_level="intermediate", sr=16000, hop_length=512):
    """Enhanced audio analysis with additional vocal features using ComprehensiveVocalAnalyzer"""
    
    
    # Initialize the comprehensive analyzer
    analyzer = ComprehensiveVocalAnalyzer(sr=sr, hop_length=hop_length)
    
    # Segment reference audio
    y_ref_seg, sr_ref = analyzer.segment_audio(reference_audio_path, match["start_time"], match["end_time"])
    y_user, sr_user = analyzer.load_audio_from_storage(user_audio_path, sr=sr)

    # Extract comprehensive features using the analyzer
    user_features = analyzer.extract_comprehensive_features(y_user)
    ref_features = analyzer.extract_comprehensive_features(y_ref_seg)
    
    # Compare features using the analyzer's comparison method
    feature_comparison = analyzer.compare_comprehensive_features(user_features, ref_features)

    # Pitch analysis - extract pitch contours and compare
    user_pitch = extract_pitch_contour(user_audio_path, sr)
    ref_pitch_segment = segment_pitch_contour(ref_pitch, sr, match["start_time"], match["end_time"], hop_length)
    dtw_result = compare_with_dtw(user_pitch, ref_pitch_segment)

    feature_comparison["pitch_dtw_distance"] = dtw_result["distance"]

    # Build comprehensive feedback using the analyzer's method
    # feedback_prompt = analyzer.build_comprehensive_feedback_prompt(
    #     " ".join(match["song_words_snippet"]), 
    #     feature_comparison,
    #     coaching_level
    # )
    
    # Make serializable using the analyzer's method
    comparison_serializable = {k: analyzer.to_serializable(v) for k, v in feature_comparison.items()}
    
    # Extract frame-level features for potential granular analysis
    user_frames = analyzer.extract_frame_level_features(y_user)
    ref_frames = analyzer.extract_frame_level_features(y_ref_seg)
    
    # Optional: Perform granular word-level analysis if lyrics are available
    granular_feedback = None
    if match.get("song_words_snippet"):
        # Align words to timestamps
        word_timestamps = analyzer.align_words_to_timestamps(
            match["song_words_snippet"], 
            0,  # Start from beginning of user audio segment
            len(y_user) / sr  # Duration of user audio
        )
        
        # Analyze each word
        word_analyses = []
        for word_timestamp in word_timestamps:
            word_analysis = analyzer.analyze_word_level_performance(
                user_frames, ref_frames, word_timestamp
            )
            if word_analysis:
                word_analyses.append(word_analysis)
        
        # Generate granular feedback
        if word_analyses:
            granular_feedback = analyzer.generate_granular_feedback(word_analyses)
    
    return {
        "matched_lyrics": match["song_words_snippet"],
        "start_time": match["start_time"],
        "end_time": match["end_time"],
       
        "comparison_metrics": comparison_serializable,
        "coaching_level": coaching_level,
        "breath_analysis": {
            "breath_count": user_features.get("breath_count", 0),
            "average_breath_duration": user_features.get("average_breath_duration", 0),
            "breath_efficiency": ref_features.get("breath_count", 1) / max(user_features.get("breath_count", 1), 1)
        },
        "technical_summary": {
            "pitch_accuracy": user_features.get("intonation_accuracy", 0),
            "vocal_stability": user_features.get("pitch_stability", 0),
            "breath_support": user_features.get("sustain_stability", 0),
            "expression_level": user_features.get("expression_variation", 0),
            "vibrato_quality": user_features.get("vibrato_regularity", 0),
            "onset_quality": user_features.get("onset_sharpness", 0),
            "voice_quality": user_features.get("voice_quality", 0),
            "dynamic_range": user_features.get("dynamic_range", 0)
        },
        "advanced_metrics": {
            "formant_clarity": user_features.get("formant_clarity", 0),
            "vowel_definition": user_features.get("vowel_definition", 0),
            "vocal_fry_amount": user_features.get("vocal_fry_amount", 0),
            "attack_time": user_features.get("attack_time", 0),
            "pitch_drift": user_features.get("pitch_drift", 0)
        },
        "granular_feedback": granular_feedback,  # Word-by-word analysis if available
        "dtw_analysis": {
            "distance": dtw_result["distance"],
            "alignment_quality": 1.0 / (1.0 + dtw_result["distance"])  # Normalized alignment score
        }
    }