# HLS Migration Plan for 360 Virtual Experience

## Executive Summary

Convert the 360 panoramic video viewer from direct MP4 streaming to HLS (HTTP Live Streaming) to solve buffering and I/O contention issues when playing 3 simultaneous 10GB video files.

---

## Current State

### Problem
- 3 x ~10GB MP4 files streaming simultaneously
- Browser makes competing range requests causing disk I/O contention
- Videos stall frequently during playback
- Buffering is unreliable and fragile

### Current Architecture
```
Browser                    Server (Python)              Disk
   │                            │                         │
   │── Range: bytes=0-10GB ────►│── Read 10GB file ──────►│
   │── Range: bytes=0-10GB ────►│── Read 10GB file ──────►│ CONTENTION!
   │── Range: bytes=0-10GB ────►│── Read 10GB file ──────►│
   │                            │                         │
```

### Files Involved
| File | Size | Purpose |
|------|------|---------|
| `videos/flight_line_1.mp4` | 9.8 GB | Panel 3 (Right) |
| `videos/flight_line_2.mp4` | 9.7 GB | Panel 2 (Center) |
| `videos/flight_line_3.mp4` | 9.7 GB | Panel 1 (Left) |
| `viewer/multi-view.html` | ~2000 lines | 3-panel viewer |
| `server.py` | ~189 lines | HTTP server with range support |

---

## Target State

### HLS Architecture
```
Browser + HLS.js            Server (Python)              Disk
   │                            │                         │
   │── GET playlist.m3u8 ──────►│── Read 2KB ────────────►│
   │◄── Segment list ───────────│                         │
   │                            │                         │
   │── GET segment_001.ts ─────►│── Read ~50MB ──────────►│ Small
   │── GET segment_001.ts ─────►│── Read ~50MB ──────────►│ Sequential
   │── GET segment_001.ts ─────►│── Read ~50MB ──────────►│ Reads!
   │                            │                         │
```

### New File Structure
```
E:\360 virtual experience\
├── videos/
│   ├── flight_line_1.mp4          # Original (keep as backup)
│   ├── flight_line_2.mp4
│   ├── flight_line_3.mp4
│   ├── hls/                        # NEW: HLS segments
│   │   ├── flight_line_1/
│   │   │   ├── playlist.m3u8      # ~5KB manifest
│   │   │   ├── segment_000.ts     # ~50MB each
│   │   │   ├── segment_001.ts
│   │   │   └── ... (~80-85 segments per video)
│   │   ├── flight_line_2/
│   │   │   ├── playlist.m3u8
│   │   │   └── segment_*.ts
│   │   └── flight_line_3/
│   │       ├── playlist.m3u8
│   │       └── segment_*.ts
├── tools/
│   └── convert_to_hls.py          # NEW: Conversion script
├── viewer/
│   └── multi-view.html            # MODIFIED: Add HLS.js
└── server.py                       # MODIFIED: Serve .m3u8 MIME type
```

---

## Implementation Plan

### Phase 1: Create HLS Conversion Script
**File:** `tools/convert_to_hls.py`

**Purpose:** Convert MP4 files to HLS format using FFmpeg

**FFmpeg Command (per video):**
```bash
ffmpeg -i flight_line_1.mp4 \
    -c:v copy \                    # No re-encoding (fast!)
    -c:a copy \                    # Copy audio as-is
    -hls_time 10 \                 # 10-second segments
    -hls_list_size 0 \             # Include all segments in playlist
    -hls_segment_filename "hls/flight_line_1/segment_%03d.ts" \
    -f hls \
    "hls/flight_line_1/playlist.m3u8"
```

**Script Features:**
- Process all 3 videos
- Progress reporting
- Error handling
- Verification of output

**Estimated Time:** 5-10 minutes per video (copy mode, no re-encode)

---

### Phase 2: Update Server for HLS
**File:** `server.py`

**Changes Required:**
1. Add MIME type for `.m3u8` files: `application/vnd.apple.mpegurl`
2. Add MIME type for `.ts` files: `video/mp2t`
3. Ensure CORS headers are present (already done)

**Code Changes:**
```python
# Add to RangeRequestHandler class
def guess_type(self, path):
    """Override to add HLS MIME types."""
    if path.endswith('.m3u8'):
        return 'application/vnd.apple.mpegurl'
    elif path.endswith('.ts'):
        return 'video/mp2t'
    return super().guess_type(path)
```

---

### Phase 3: Update Viewer for HLS
**File:** `viewer/multi-view.html`

**Changes Required:**

#### 3.1 Add HLS.js Library
```html
<!-- Add before </head> -->
<script src="https://cdn.jsdelivr.net/npm/hls.js@1.5.7"></script>
```

#### 3.2 Update Video URLs
```javascript
// OLD (line 871-876)
const videoUrls = [
    '/videos/flight_line_3.mp4',
    '/videos/flight_line_2.mp4',
    '/videos/flight_line_1.mp4'
];

// NEW
const videoUrls = [
    '/videos/hls/flight_line_3/playlist.m3u8',
    '/videos/hls/flight_line_2/playlist.m3u8',
    '/videos/hls/flight_line_1/playlist.m3u8'
];
```

#### 3.3 Add HLS Loading Method to Viewer360 Class
```javascript
loadVideo() {
    if (this.videoUrl.endsWith('.m3u8') && Hls.isSupported()) {
        // HLS.js for browsers that don't natively support HLS
        this.hls = new Hls({
            maxBufferLength: 30,           // Buffer 30 seconds ahead
            maxMaxBufferLength: 60,        // Max 60 seconds buffer
            startLevel: -1,                // Auto quality selection
            debug: false
        });
        this.hls.loadSource(this.videoUrl);
        this.hls.attachMedia(this.video);
        this.hls.on(Hls.Events.MANIFEST_PARSED, () => {
            Logger.video(`Panel ${this.index + 1}: HLS manifest loaded`);
        });
        this.hls.on(Hls.Events.ERROR, (event, data) => {
            Logger.error(`Panel ${this.index + 1}: HLS error`, data.type, data.details);
        });
    } else if (this.video.canPlayType('application/vnd.apple.mpegurl')) {
        // Native HLS support (Safari)
        this.video.src = this.videoUrl;
    } else {
        // Fallback to direct MP4 (won't work well, but provides fallback)
        this.video.src = this.videoUrl;
    }
    this.video.load();
}
```

#### 3.4 Simplify Video Loading Logic
Replace the complex buffering logic with simple HLS loading:

```javascript
function initViewers() {
    const panels = document.querySelectorAll('.viewer-panel');

    // Create all viewers
    panels.forEach((panel, index) => {
        const viewer = new Viewer360(panel, videoUrls[index], index, false);
        viewers.push(viewer);
    });

    Logger.info('Loading HLS streams...');

    let loadedCount = 0;

    viewers.forEach((viewer, index) => {
        // HLS.js handles buffering automatically
        viewer.loadVideo();

        viewer.video.addEventListener('canplay', () => {
            loadedCount++;
            Logger.video(`Panel ${index + 1}: Ready (${loadedCount}/3)`);

            if (loadedCount === viewers.length) {
                document.getElementById('loading-overlay').classList.add('hidden');
                Logger.info('All streams ready - starting synchronized playback');

                // Sync to start and play
                viewers.forEach(v => v.video.currentTime = 0);
                setTimeout(() => playAll(), 100);
            }
        }, { once: true });
    });

    // Fallback timeout
    setTimeout(() => {
        if (!document.getElementById('loading-overlay').classList.contains('hidden')) {
            document.getElementById('loading-overlay').classList.add('hidden');
            Logger.warn('Timeout - starting with available streams');
            playAll();
        }
    }, 15000);
}
```

#### 3.5 Add HLS Cleanup on Destroy
```javascript
// Add to Viewer360 class
destroy() {
    if (this.hls) {
        this.hls.destroy();
        this.hls = null;
    }
    // ... existing cleanup
}
```

---

### Phase 4: Testing & Verification

#### Test Cases
1. **Initial Load**: All 3 panels should load and display first frame
2. **Synchronized Playback**: Videos should start together
3. **Seeking**: Jump to any point should be fast (~1-2 seconds)
4. **No Stalls**: Playback should be smooth without buffering interruptions
5. **Sync Drift**: Videos should stay in sync (< 500ms drift)
6. **Controls**: All existing controls should work unchanged

#### Verification Commands
```bash
# Check HLS output was created correctly
dir /s "E:\360 virtual experience\videos\hls"

# Verify segment count matches expected duration
# ~830 seconds / 10 seconds per segment = ~83 segments per video
```

---

## Rollback Plan

If HLS doesn't work as expected:

1. **Keep original MP4 files** - Don't delete them
2. **Revert video URLs** in multi-view.html
3. **Remove HLS.js script** tag
4. **Restore old loadVideo()** method

The server changes are backwards compatible (just adds MIME types).

---

## Timeline Estimate

| Phase | Task | Time |
|-------|------|------|
| 1 | Create conversion script | 15 min |
| 1 | Run conversion (3 videos) | 15-30 min |
| 2 | Update server.py | 5 min |
| 3 | Update multi-view.html | 30 min |
| 4 | Testing & debugging | 30 min |
| **Total** | | **~1.5-2 hours** |

---

## Disk Space Requirements

| Item | Size |
|------|------|
| Original MP4s | 29.2 GB |
| HLS Segments (copy mode) | ~29.2 GB |
| **Total during conversion** | ~58.4 GB |
| **After deleting originals** | ~29.2 GB |

**Recommendation:** Keep originals until HLS is verified working, then optionally delete to reclaim space.

---

## Success Criteria

1. ✅ All 3 videos load within 10 seconds
2. ✅ Playback is smooth with no buffering stalls
3. ✅ Seeking is responsive (< 2 seconds)
4. ✅ Videos stay synchronized (drift < 500ms)
5. ✅ All existing controls work unchanged
6. ✅ Debug logging shows clean HLS events

---

## Files to Create/Modify

### New Files
- `tools/convert_to_hls.py` - Conversion script

### Modified Files
- `server.py` - Add HLS MIME types
- `viewer/multi-view.html` - Add HLS.js, update video loading

### Generated Files (by conversion)
- `videos/hls/flight_line_1/playlist.m3u8`
- `videos/hls/flight_line_1/segment_*.ts` (~83 files)
- `videos/hls/flight_line_2/playlist.m3u8`
- `videos/hls/flight_line_2/segment_*.ts` (~83 files)
- `videos/hls/flight_line_3/playlist.m3u8`
- `videos/hls/flight_line_3/segment_*.ts` (~83 files)

---

## Next Steps

1. Review and approve this plan
2. Execute Phase 1: Create and run conversion script
3. Execute Phase 2: Update server
4. Execute Phase 3: Update viewer
5. Execute Phase 4: Test and verify
