"""Step 3 — select the best short-form clips from a transcript.

Hybrid approach:
1. Deterministic candidate generation with engagement signal scoring
2. Optional semantic ranking using sentence-transformers (if available)
3. Strict transcript-grounded validation

The system NEVER invents timestamps — all start/end values come directly
from transcript segment boundaries. The semantic model only ranks candidates,
it does NOT choose or modify timestamps.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import config


class AnalysisError(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# Engagement signal keywords
# ---------------------------------------------------------------------------

# Strong engagement words (each adds +1 to segment score)
ENGAGEMENT_KEYWORDS = frozenset([
    # Emotional / surprising
    "shocking", "amazing", "insane", "crazy", "wild", "unbelievable",
    "incredible", "mind-blowing", "jaw-dropping", "hilarious",
    # Controversy / debate
    "controversial", "debate", "argument", "fight", "destroy", "destroyed",
    "worst", "best", "never", "always", "lie", "truth", "fake",
    # Curiosity / secrets
    "secret", "hidden", "truth", "real", "actually", "honestly",
    "nobody tells", "they don't want", "you won't believe",
    # Action / urgency
    "must", "need", "important", "critical", "urgent", "stop",
    "warning", "danger", "risk", "consequence",
    # Storytelling
    "story", "happened", "moment", "experience", "remember",
    "first time", "last time", "turns out",
])

# Strong hook words at segment start (each adds +3)
STRONG_HOOK_WORDS = frozenset([
    "so", "but", "actually", "honestly", "look", "listen",
    "here's", "this is", "the thing", "the problem", "the truth",
    "let me", "i need", "you need", "we need", "stop", "wait",
    "okay so", "so basically", "the crazy thing", "nobody knows",
    "listen to this", "you won't believe", "this is insane",
])

# Weak conversational openings to penalize (score -4)
WEAK_OPENINGS = frozenset([
    "okay", "yeah", "yes", "no", "i don't know", "you know",
    "like", "well", "so", "and", "but", "or", "um", "uh",
    "hmm", "oh", "right", "sure", "cool", "nice", "wow",
])

# Interview-specific engagement signals
INTERVIEW_SIGNALS = frozenset([
    # Strong reactions
    "that's insane", "that's crazy", "that's wild", "oh my god",
    "no way", "are you serious", "wait what", "shut up",
    # Surprising answers
    "actually", "believe it or not", "surprisingly", "turns out",
    # Funny exchanges
    "hilarious", "funny", "laughing", "joke", "haha",
    # Emotional stories
    "i remember", "i was like", "she said", "he told me",
    "the moment", "that day", "that time",
    # Controversial claims
    "controversial", "unpopular opinion", "hot take", "debate",
    # Question-answer moments
    "the answer is", "here's the thing", "let me explain",
])

# Filler/intro patterns to penalize (score -3)
FILLER_PATTERNS = [
    re.compile(r"^(hey|hi|hello|welcome|what's up|how's it going)", re.I),
    re.compile(r"^(good morning|good evening|good afternoon)", re.I),
    re.compile(r"^(before we start|let's get started|without further ado)", re.I),
    re.compile(r"^(don't forget to|make sure to|subscribe)", re.I),
    re.compile(r"^(like and share|smash that|hit the)", re.I),
]

# Incomplete/context-dependent patterns (score -2)
INCOMPLETE_PATTERNS = [
    re.compile(r"^(he|she|it|they|this|that|these|those)\s+(said|says|did|was|is|are)", re.I),
    re.compile(r"^(and then|so then|after that|before that)", re.I),
    re.compile(r"^(it's|that's|there's|here's)\s+(a|an|the)\s+\w+$", re.I),
]

# Pronouns/references that indicate the segment needs preceding context
NEEDS_CONTEXT_PATTERNS = [
    re.compile(r"^(he|she|it|they|this|that|these|those|we|you|i)\s+(said|says|did|was|is|are|had|have|has|would|could|should|might|will)", re.I),
    re.compile(r"^(and then|so then|after that|before that|because of|as a result)", re.I),
    re.compile(r"^(yeah|right|exactly|totally|absolutely)\b", re.I),
]

# Patterns that suggest a clip is a standalone thought (score +2)
STANDALONE_PATTERNS = [
    re.compile(r"^(so|but|look|listen|here's the thing|the truth is|let me)", re.I),
    re.compile(r"^(i think|i believe|in my opinion|the problem is)", re.I),
    re.compile(r"^(what if|what happens|did you know|fun fact)", re.I),
    re.compile(r"^(never|always|everyone|nobody|the best|the worst)", re.I),
]

# Patterns that suggest a natural ending (score +2)
NATURAL_ENDING_PATTERNS = [
    re.compile(r"[.!?]$"),
    re.compile(r"(that's|it's) (it|all|the whole story|the thing|how it works)", re.I),
    re.compile(r"(so|and) (that's|that is) (why|how|what)", re.I),
]


# ---------------------------------------------------------------------------
# Candidate window data structure
# ---------------------------------------------------------------------------

@dataclass
class Candidate:
    """A candidate clip window with its transcript segments."""
    start_seg_idx: int          # Index of first segment
    end_seg_idx: int            # Index of last segment (inclusive)
    start_time: float           # From segments[start_seg_idx]["start"]
    end_time: float             # From segments[end_seg_idx]["end"]
    duration: float             # end_time - start_time
    score: float = 0.0          # Deterministic engagement score
    semantic_score: float = 0.0 # Semantic ranking score (0 if not computed)
    texts: list[str] = field(default_factory=list)  # Text of segments in window


# ---------------------------------------------------------------------------
# Phase 1: Deterministic candidate generation
# ---------------------------------------------------------------------------

def _score_hook(text: str) -> float:
    """Score the opening hook of a segment. Strong hooks get high scores."""
    score = 0.0
    text_lower = text.lower().strip()
    words = text_lower.split()
    first_3_words = " ".join(words[:3]) if words else ""
    first_5_words = " ".join(words[:5]) if words else ""

    # Penalize weak openings strongly (-4)
    if text_lower in WEAK_OPENINGS or first_3_words in WEAK_OPENINGS:
        score -= 4
    elif any(text_lower.startswith(w) for w in ["okay", "yeah", "yes", "no", "well", "like", "so"]):
        score -= 3

    # Reward strong hook words (+3)
    if any(hw in first_5_words for hw in STRONG_HOOK_WORDS):
        score += 3

    # Strong claims (+2)
    if re.search(r"\b(always|never|everyone|nobody|everything|nothing|best|worst|most|least)\b", text_lower):
        score += 2

    # Surprising statements (+2)
    if re.search(r"\b(insane|crazy|wild|unbelievable|incredible|shocking|amazing)\b", text_lower):
        score += 2

    # Questions that create curiosity (+2)
    if text.rstrip().endswith("?"):
        score += 2

    # Emotional language (+1)
    if re.search(r"\b(love|hate|fear|angry|sad|happy|excited|terrified)\b", text_lower):
        score += 1

    # Numbers/statistics (+1)
    if re.search(r"\b\d+\b", text):
        score += 1

    # Personal stories (+1)
    if re.search(r"\b(i was|i had|i remember|she said|he told me)\b", text_lower):
        score += 1

    # Controversy/humor (+1)
    if any(w in text_lower for w in ["controversial", "debate", "funny", "hilarious", "lie", "truth"]):
        score += 1

    # Standalone patterns (+2) — clips that can be understood without context
    for pat in STANDALONE_PATTERNS:
        if pat.search(text_lower):
            score += 2
            break

    return score


def _score_segment(text: str, seg_idx: int, total_segs: int) -> float:
    """Score a single segment for engagement signals."""
    score = 0.0
    text_lower = text.lower()
    words = text_lower.split()

    # Engagement keywords (+1 each, max +5)
    kw_hits = sum(1 for kw in ENGAGEMENT_KEYWORDS if kw in text_lower)
    score += min(kw_hits, 5)

    # Interview-specific signals (+2 each, max +4)
    interview_hits = sum(1 for sig in INTERVIEW_SIGNALS if sig in text_lower)
    score += min(interview_hits * 2, 4)

    # Questions and exclamations (+1 each)
    if "?" in text:
        score += 1
    if "!" in text:
        score += 1

    # Numbers/statistics (+1)
    if re.search(r"\d+", text):
        score += 1

    # First-person stories (+1)
    if re.search(r"\b(i |i'm |i've |i was |i had |my )", text_lower):
        score += 1

    # Longer segments with more content (+1 if >15 words)
    if len(words) > 15:
        score += 1

    # Conversational intensity: multiple clauses (+1)
    if text.count(",") >= 2 or text.count("—") >= 1:
        score += 1

    # Penalize filler/intros (-3)
    for pat in FILLER_PATTERNS:
        if pat.search(text):
            score -= 3
            break

    # Penalize incomplete/context-dependent segments (-2)
    for pat in INCOMPLETE_PATTERNS:
        if pat.search(text):
            score -= 2
            break

    # Penalize very short segments (< 3 words) (-1)
    if len(words) < 3:
        score -= 1

    # Bonus for segments in the middle 80% of the video (avoid edges)
    if total_segs > 5:
        position_frac = seg_idx / total_segs
        if 0.1 <= position_frac <= 0.9:
            score += 0.5

    return score


def _generate_candidates(
    segments: list[dict],
    duration: float,
) -> list[Candidate]:
    """Generate candidate clip windows from transcript segments.

    Generates candidates in multiple duration ranges to ensure we get
    a mix of short punchy clips and longer narrative clips.
    All timestamps come directly from segment boundaries.
    """
    if not segments:
        return []

    min_dur = config.CLIP_MIN_SECONDS
    max_dur = config.CLIP_MAX_SECONDS
    candidates = []

    # Pre-compute segment scores
    seg_scores = [
        _score_segment(s["text"], i, len(segments))
        for i, s in enumerate(segments)
    ]

    # Slide window: for each possible start segment, find valid end segments
    for start_idx in range(len(segments)):
        window_score = 0.0
        window_texts = []
        hook_score = _score_hook(segments[start_idx]["text"])

        for end_idx in range(start_idx, len(segments)):
            seg = segments[end_idx]
            seg_dur = seg["end"] - segments[start_idx]["start"]

            # Stop if window exceeds maximum duration (STRICT)
            if seg_dur > max_dur:
                break

            # Add this segment to the window
            window_score += seg_scores[end_idx]
            window_texts.append(seg["text"])

            # Only create candidates that meet minimum duration (STRICT)
            if seg_dur >= min_dur:
                c = Candidate(
                    start_seg_idx=start_idx,
                    end_seg_idx=end_idx,
                    start_time=segments[start_idx]["start"],
                    end_time=seg["end"],
                    duration=seg_dur,
                    score=window_score + hook_score,
                    texts=list(window_texts),
                )
                candidates.append(c)

                # Context expansion: if the opening segment needs context
                # (starts with pronouns, "and then", etc.), create an
                # expanded variant that includes the preceding segment.
                first_text = segments[start_idx]["text"].lower().strip()
                needs_ctx = any(pat.search(first_text) for pat in NEEDS_CONTEXT_PATTERNS)
                if needs_ctx and start_idx > 0 and end_idx == start_idx + max(0, int(min_dur / 5)):
                    prev = segments[start_idx - 1]
                    expanded_dur = seg["end"] - prev["start"]
                    if min_dur <= expanded_dur <= max_dur:
                        candidates.append(Candidate(
                            start_seg_idx=start_idx - 1,
                            end_seg_idx=end_idx,
                            start_time=prev["start"],
                            end_time=seg["end"],
                            duration=expanded_dur,
                            score=window_score + hook_score + 3,  # context bonus
                            texts=[prev["text"]] + list(window_texts),
                        ))

    return candidates


# ---------------------------------------------------------------------------
# Phase 2a: Deterministic ranking
# ---------------------------------------------------------------------------

def _rank_deterministic(candidates: list[Candidate]) -> list[Candidate]:
    """Rank candidates by deterministic engagement score.

    Uses engagement density (score per second) to prefer punchy clips,
    but preserves longer clips when they have strong narrative signals.
    """
    for c in candidates:
        if c.duration > 0:
            # Base score: engagement density (score / sqrt(duration))
            density = c.score / (c.duration ** 0.5)

            # Bonus for shorter clips (15-30s) — they're punchier for Shorts
            if c.duration <= 30:
                density *= 1.2  # 20% bonus for short clips
            elif c.duration <= 45:
                density *= 1.1  # 10% bonus for medium clips
            # No bonus for 45-60s clips (they need stronger content to win)

            # Bonus for clips with natural endings (+15%)
            last_text = c.texts[-1].strip() if c.texts else ""
            if last_text and last_text[-1] in '.!?':
                density *= 1.15

            c.score = density

    # Sort by score descending
    candidates.sort(key=lambda c: c.score, reverse=True)
    return candidates


def _select_non_overlapping(
    candidates: list[Candidate],
    max_clips: int,
) -> list[Candidate]:
    """Select top non-overlapping candidates."""
    selected = []
    for c in candidates:
        if len(selected) >= max_clips:
            break

        # Check overlap with already-selected clips
        overlap = False
        for s in selected:
            overlap_start = max(c.start_time, s.start_time)
            overlap_end = min(c.end_time, s.end_time)
            overlap_dur = overlap_end - overlap_start
            if overlap_dur > 0.2 * c.duration:
                overlap = True
                break

        if not overlap:
            selected.append(c)

    return selected


# ---------------------------------------------------------------------------
# Phase 2b: Semantic ranking (optional)
# ---------------------------------------------------------------------------

_model_cache = None


def _load_semantic_model():
    """Load the sentence-transformers model. Returns None if unavailable."""
    global _model_cache
    if _model_cache is not None:
        return _model_cache

    try:
        from sentence_transformers import SentenceTransformer
        _model_cache = SentenceTransformer("paraphrase-MiniLM-L3-v2")
        return _model_cache
    except ImportError:
        return None
    except Exception:
        return None


def _rank_semantic(
    candidates: list[Candidate],
    model,
) -> list[Candidate]:
    """Rank candidates by semantic similarity to engagement anchors.

    The model encodes candidate texts and compares them to hand-crafted
    "engaging content" anchor phrases. Candidates most similar to
    engaging content get higher scores.
    """
    # Anchor phrases describing engaging content
    anchors = [
        "a shocking revelation that changes everything",
        "an intense emotional moment of conflict",
        "a surprising twist that nobody expected",
        "a funny hilarious moment that makes you laugh",
        "an important useful tip that helps you",
        "a controversial debate about a hot topic",
        "a dramatic story with a powerful ending",
        "a mind-blowing fact that surprises everyone",
        "an inspiring moment of personal growth",
        "a crazy wild moment of pure chaos",
    ]

    # Encode anchors once
    anchor_embeddings = model.encode(anchors, convert_to_tensor=True)

    # Encode candidate texts
    candidate_texts = [" ".join(c.texts[:5]) for c in candidates]  # First 5 segments
    if not candidate_texts:
        return candidates

    candidate_embeddings = model.encode(candidate_texts, convert_to_tensor=True)

    # Compute cosine similarity with each anchor
    import torch
    similarities = torch.nn.functional.cosine_similarity(
        candidate_embeddings.unsqueeze(1),
        anchor_embeddings.unsqueeze(0),
        dim=2,
    )

    # Max similarity across anchors for each candidate
    max_sim, _ = similarities.max(dim=1)

    # Combine with deterministic score (70% semantic, 30% deterministic)
    for i, c in enumerate(candidates):
        c.semantic_score = float(max_sim[i])
        c.score = 0.3 * c.score + 0.7 * c.semantic_score

    candidates.sort(key=lambda c: c.score, reverse=True)
    return candidates


# ---------------------------------------------------------------------------
# Phase 3: Metadata generation (deterministic)
# ---------------------------------------------------------------------------

def _generate_metadata(candidate: Candidate) -> dict:
    """Generate clip metadata from transcript text.

    All metadata is derived from the actual transcript content.
    Nothing is invented.
    """
    # Combine all text in the clip
    full_text = " ".join(candidate.texts)
    sentences = re.split(r"[.!?]+", full_text)
    sentences = [s.strip() for s in sentences if s.strip()]

    # Hook: first meaningful sentence (verbatim from transcript)
    hook = candidate.texts[0] if candidate.texts else ""
    hook = hook[:200]

    # Title: first 5-8 words, cleaned up
    words = full_text.split()
    title_words = words[:8] if len(words) > 8 else words
    title = " ".join(title_words)
    if len(title) > 80:
        title = title[:77] + "..."

    # Reason: template based on engagement signals
    reasons = []
    if "?" in full_text:
        reasons.append("poses an engaging question")
    if "!" in full_text:
        reasons.append("contains emphatic statements")
    kw_hits = [kw for kw in ENGAGEMENT_KEYWORDS if kw in full_text.lower()]
    if kw_hits:
        reasons.append(f"features engaging language ({kw_hits[0]})")
    if re.search(r"\d+", full_text):
        reasons.append("includes specific numbers or facts")
    if not reasons:
        reasons.append("contains substantive content")
    reason = f"This moment {reasons[0]}." if reasons else "Selected for engagement potential."

    # Post title: cleaned version of title for YouTube Shorts
    post_title = title[:90]

    # Description: hook + CTA
    description = f"{hook}. Watch the full video for more context."

    # Hashtags: extract keywords from text
    # Remove common words, take top 5 unique words
    stop_words = frozenset([
        "the", "a", "an", "is", "are", "was", "were", "be", "been",
        "have", "has", "had", "do", "does", "did", "will", "would",
        "could", "should", "may", "might", "shall", "can", "to", "of",
        "in", "for", "on", "with", "at", "by", "from", "as", "into",
        "through", "during", "before", "after", "above", "below",
        "and", "but", "or", "nor", "not", "so", "if", "then",
        "that", "this", "these", "those", "it", "its", "i", "you",
        "he", "she", "we", "they", "me", "him", "us", "them",
        "my", "your", "his", "her", "our", "their", "mine", "yours",
    ])
    word_freq = {}
    for w in words:
        w_clean = re.sub(r"[^a-zA-Z0-9]", "", w.lower())
        if w_clean and len(w_clean) > 2 and w_clean not in stop_words:
            word_freq[w_clean] = word_freq.get(w_clean, 0) + 1

    top_words = sorted(word_freq.keys(), key=lambda w: word_freq[w], reverse=True)[:5]
    hashtags = [f"#{w}" for w in top_words]
    if "#shorts" not in hashtags:
        hashtags.insert(0, "#shorts")
    hashtags = hashtags[:6]

    return {
        "title": title,
        "hook": hook,
        "reason": reason,
        "post_title": post_title,
        "description": description,
        "hashtags": hashtags,
    }


# ---------------------------------------------------------------------------
# Phase 4: Validation
# ---------------------------------------------------------------------------

def _validate_clip(
    candidate: Candidate,
    segments: list[dict],
    duration: float,
    seen_ranges: list[tuple[float, float]],
) -> dict | None:
    """Validate a candidate and return a clean clip dict.

    STRICT RULES:
    - Timestamps MUST come from transcript segment boundaries
    - Duration MUST be within configured limits
    - Must not overlap excessively with already-selected clips
    """
    # Verify segment indices are valid
    if candidate.start_seg_idx < 0 or candidate.start_seg_idx >= len(segments):
        return None
    if candidate.end_seg_idx < 0 or candidate.end_seg_idx >= len(segments):
        return None
    if candidate.start_seg_idx > candidate.end_seg_idx:
        return None

    # Verify timestamps match transcript exactly
    actual_start = segments[candidate.start_seg_idx]["start"]
    actual_end = segments[candidate.end_seg_idx]["end"]

    # Timestamps MUST come from transcript (strict check)
    if abs(candidate.start_time - actual_start) > 0.01:
        return None
    if abs(candidate.end_time - actual_end) > 0.01:
        return None

    # Clamp to video duration
    if duration > 0:
        actual_end = min(actual_end, duration)
    actual_start = max(0.0, actual_start)

    length = actual_end - actual_start
    # STRICT duration enforcement: must be within configured limits
    if length < config.CLIP_MIN_SECONDS:
        return None
    if length > config.CLIP_MAX_SECONDS:
        return None

    # Check overlap with already-selected clips
    for prev_start, prev_end in seen_ranges:
        overlap = min(prev_end, actual_end) - max(prev_start, actual_start)
        if overlap > 0.2 * length:
            return None

    # Cold-viewer test: can this clip be understood without the source video?
    full_text = " ".join(candidate.texts).lower().strip()
    words = full_text.split()

    # Hard reject: too few words to be meaningful
    if len(words) < 5:
        return None

    # Hard reject: clip is just filler/intro with no real content
    is_filler = any(pat.search(full_text) for pat in FILLER_PATTERNS)
    if is_filler and len(words) < 8:
        return None

    # Bonus for natural ending (ends with punctuation or natural phrase)
    last_text = candidate.texts[-1].strip() if candidate.texts else ""
    has_natural_end = bool(last_text and last_text[-1] in '.!?')
    if not has_natural_end:
        for pat in NATURAL_ENDING_PATTERNS:
            if pat.search(full_text):
                has_natural_end = True
                break

    # Generate metadata
    metadata = _generate_metadata(candidate)

    return {
        "start": round(actual_start, 2),
        "end": round(actual_end, 2),
        "standalone": True,
        "natural_ending": has_natural_end,
        **metadata,
    }


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def find_clips(
    title: str,
    duration: float,
    segments: list[dict],
    max_clips: int,
) -> list[dict]:
    """Select the best short-form clips from a numbered transcript.

    HYBRID APPROACH:
    1. Generate candidate windows deterministically
    2. Rank by engagement signals (deterministic)
    3. Optionally re-rank by semantic similarity (if model available)
    4. Select top non-overlapping candidates
    5. Generate metadata from transcript text
    6. Validate all timestamps come from transcript

    The system NEVER invents timestamps — all start/end values
    come directly from transcript segment boundaries.
    """
    if not segments:
        raise AnalysisError("No transcript segments provided.")

    # Phase 1: Generate candidates
    candidates = _generate_candidates(segments, duration)
    if not candidates:
        raise AnalysisError(
            f"No valid candidate windows found. "
            f"Video duration: {duration:.0f}s. "
            f"Segments: {len(segments)}. "
            f"Min clip length: {config.CLIP_MIN_SECONDS:.0f}s."
        )

    # Phase 2a: Deterministic ranking
    candidates = _rank_deterministic(candidates)

    # Phase 2b: Semantic ranking (optional — if model is available)
    model = _load_semantic_model()
    if model is not None:
        try:
            candidates = _rank_semantic(candidates, model)
        except Exception:
            pass  # Fall back to deterministic ranking

    # Phase 3: Select non-overlapping top candidates
    selected = _select_non_overlapping(candidates, max_clips)

    # Phase 4: Validate and build output
    cleaned = []
    seen_ranges: list[tuple[float, float]] = []

    for candidate in selected:
        clip = _validate_clip(candidate, segments, duration, seen_ranges)
        if clip is not None:
            cleaned.append(clip)
            seen_ranges.append((clip["start"], clip["end"]))

    if not cleaned:
        raise AnalysisError(
            f"Generated {len(candidates)} candidates, but none passed "
            f"validation. Video duration: {duration:.0f}s. "
            f"Segments: {len(segments)}. "
            f"Min clip length: {config.CLIP_MIN_SECONDS:.0f}s."
        )

    return cleaned[:max_clips]
