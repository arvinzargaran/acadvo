#!/usr/bin/env bash
# Turn the recorded landing-page scroll into the two files the README needs.
#
#   scripts/record-landing.mjs      -> docs/media/landing.webm
#   scripts/convert-landing.sh      -> docs/media/landing.gif + landing.mp4
#
# The GIF is what GitHub actually plays inline: a committed .mp4 referenced from
# markdown renders as a link, not a player. The mp4 is kept anyway because it is
# a third of the size at better quality for anywhere that can play one.
#
# Requires ffmpeg (brew install ffmpeg).
set -euo pipefail

SRC="docs/media/landing.webm"
OUT_GIF="docs/media/landing.gif"
OUT_MP4="docs/media/landing.mp4"
PALETTE="$(mktemp -t landing-palette).png"

# Playback speed. The recording pauses on each section so its reveal animation
# can finish, which is right for watching and too slow for a loop; halving the
# timestamps keeps every settled frame and drops the dead air.
SPEED="${SPEED:-0.5}"
WIDTH="${WIDTH:-800}"
FPS="${FPS:-10}"
COLORS="${COLORS:-96}"

[ -f "$SRC" ] || { echo "missing $SRC — run: node scripts/record-landing.mjs" >&2; exit 1; }

FILTERS="setpts=${SPEED}*PTS,fps=${FPS},scale=${WIDTH}:-1:flags=lanczos"

# Two passes: one to choose a palette from the whole clip, one to apply it.
# A single pass would quantise each frame independently and the flat editorial
# colours would crawl between frames.
ffmpeg -y -loglevel error -i "$SRC" \
  -vf "${FILTERS},palettegen=max_colors=${COLORS}:stats_mode=diff" "$PALETTE"

ffmpeg -y -loglevel error -i "$SRC" -i "$PALETTE" \
  -lavfi "${FILTERS}[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle" \
  "$OUT_GIF"

ffmpeg -y -loglevel error -i "$SRC" \
  -vcodec libx264 -crf 24 -preset slow -pix_fmt yuv420p -movflags +faststart "$OUT_MP4"

rm -f "$PALETTE"

printf '%s  %s\n' "$(du -h "$OUT_GIF" | cut -f1)" "$OUT_GIF"
printf '%s  %s\n' "$(du -h "$OUT_MP4" | cut -f1)" "$OUT_MP4"
