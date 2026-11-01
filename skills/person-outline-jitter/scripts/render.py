#!/usr/bin/env python3
"""Per-frame person segmentation with a gently boiling dashed outer contour."""
import argparse
import json
import math
import shutil
import subprocess
from fractions import Fraction
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent


def run(*args):
    subprocess.run([str(x) for x in args], check=True)


def probe(path):
    return json.loads(subprocess.check_output([
        'ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(path)]))


def resample(contour, count=512):
    pts = contour[:, 0, :].astype(float)
    pts = np.vstack((pts, pts[0]))
    distances = np.r_[0, np.cumsum(np.linalg.norm(np.diff(pts, axis=0), axis=1))]
    if distances[-1] < 1:
        return None, 0
    positions = np.linspace(0, distances[-1], count, endpoint=False)
    points = np.column_stack([np.interp(positions, distances, pts[:, j]) for j in range(2)])
    # Small cyclic spatial filter removes segmentation stair steps, without time lag.
    points = sum(np.roll(points, i, axis=0) for i in range(-3, 4)) / 7
    return points, distances[-1]


class Outline:
    def __init__(self, width, height, stroke, offset, jitter):
        self.width, self.height = width, height
        self.stroke, self.offset, self.jitter = stroke, offset, jitter
        self.previous = None
        self.dashes = None

    def draw(self, mask, time):
        binary = (mask >= 128).astype(np.uint8) * 255
        n, labels, stats, _ = cv2.connectedComponentsWithStats(binary)
        alpha = np.zeros_like(binary)
        if n < 2:
            self.previous = None
            self.dashes = None
            return alpha, 0, False
        order = np.argsort(stats[1:, cv2.CC_STAT_AREA])[::-1] + 1
        area = int(stats[order[0], cv2.CC_STAT_AREA])
        if area < binary.size * .002:
            self.previous = None
            self.dashes = None
            return alpha, 0, False
        ambiguous = len(order) > 1 and stats[order[1], cv2.CC_STAT_AREA] > area * .3
        subject = (labels == order[0]).astype(np.uint8) * 255
        radius = max(1, round(self.offset + self.stroke / 2))
        expanded = cv2.dilate(subject, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2*radius+1, 2*radius+1)))
        contours, _ = cv2.findContours(expanded, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        contour = max(contours, key=cv2.contourArea)
        points, perimeter = resample(contour)
        if points is None:
            return alpha, area, ambiguous
        if self.previous is not None:
            # Match contour phase, so topmost-point changes do not rotate all the dashes.
            a = points - points.mean(axis=0)
            b = self.previous - self.previous.mean(axis=0)
            errors = [np.mean((np.roll(a, i, axis=0)-b)**2) for i in range(len(a))]
            points = np.roll(points, int(np.argmin(errors)), axis=0)
        else:
            points = np.roll(points, -int(np.argmin(points[:, 1])), axis=0)
        self.previous = points.copy()
        if self.dashes is None:
            self.dashes = max(8, round(perimeter / (74 * min(self.width, self.height) / 1080)))
        tangent = np.roll(points, -1, axis=0) - np.roll(points, 1, axis=0)
        normal = np.column_stack((-tangent[:, 1], tangent[:, 0]))
        normal /= np.maximum(np.linalg.norm(normal, axis=1)[:, None], 1e-5)
        phase = np.arange(len(points)) / len(points) * 2 * math.pi
        tick = math.floor(time * 8)
        wiggle = self.jitter * (.65*np.sin(phase*13 + tick*1.31) + .35*np.sin(phase*23 - tick*.93))
        points += normal * wiggle[:, None]
        # Dash phase is fixed: only small shape/width changes, never marching ants.
        thickness = max(2, round(self.stroke * (1 + .055*math.sin(tick*1.7))))
        closed = np.vstack((points, points[0]))
        domain = np.linspace(0, 1, len(closed))
        for i in range(self.dashes):
            positions = np.linspace(i/self.dashes, (i+.55)/self.dashes, 16)
            pts = np.rint(np.column_stack([np.interp(positions, domain, closed[:, j]) for j in range(2)])).astype(np.int32)
            cv2.polylines(alpha, [pts], False, 255, thickness, cv2.LINE_AA)
            for end in (pts[0], pts[-1]):
                cv2.circle(alpha, tuple(end), max(1, thickness//2), 255, -1, cv2.LINE_AA)
        # Never paint over a person, even where smoothing bridges a concavity.
        clearance = cv2.distanceTransform(255-binary, cv2.DIST_L2, 5)
        alpha[clearance < max(1, self.offset*.45)] = 0
        # A subject leaving the frame has no artificial closing border at the crop.
        edge = max(2, math.ceil(thickness/2 + self.jitter + 2))
        alpha[:edge] = 0
        alpha[-edge:] = 0
        alpha[:, :edge] = 0
        alpha[:, -edge:] = 0
        return alpha, area, ambiguous


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--video', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path, help='New directory; existing output is never overwritten')
    p.add_argument('--start', type=float, default=0)
    p.add_argument('--duration', type=float)
    p.add_argument('--width', type=int, help='Optional resize; otherwise retain source dimensions')
    p.add_argument('--stroke', type=float, default=12, help='Stroke px at 1080 short edge')
    p.add_argument('--offset', type=float, default=16, help='Gap px at 1080 short edge')
    p.add_argument('--jitter', type=float, default=2.4, help='Subtle hand-drawn displacement at 1080 short edge')
    p.add_argument('--mask-dir', type=Path, help='Optional exact per-frame grayscale PNG masks matching normalized video')
    a = p.parse_args()
    if a.start < 0 or (a.duration is not None and a.duration <= 0):
        p.error('Invalid time range')
    if a.stroke <= 0 or a.offset < 0 or a.jitter < 0 or (a.width is not None and a.width < 64):
        p.error('Invalid geometry')
    for exe in ('ffmpeg', 'ffprobe'):
        if not shutil.which(exe):
            p.error(f'Missing {exe}')
    if not a.mask_dir and not shutil.which('swift'):
        p.error('Automatic segmentation requires macOS + Swift; otherwise supply --mask-dir')
    info = probe(a.video)
    video = next(s for s in info['streams'] if s['codec_type'] == 'video')
    if video.get('color_transfer') in ('smpte2084', 'arib-std-b67'):
        p.error('HDR input: explicitly tone-map to SDR before running; do not silently wash out colors')
    fps = Fraction(video['avg_frame_rate'])
    if not 1 <= float(fps) <= 120:
        p.error('Unsupported frame rate')
    if a.start >= float(info['format']['duration']):
        p.error('Start outside source')
    a.output.mkdir(parents=True, exist_ok=False)
    source = a.output / 'source.mp4'
    filters = [f'fps={fps}']
    if a.width:
        filters.append(f'scale={a.width}:-2')
    filters.extend(['pad=ceil(iw/2)*2:ceil(ih/2)*2', 'setsar=1'])
    cmd = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-nostdin', '-ss', a.start, '-i', a.video]
    if a.duration:
        cmd += ['-t', a.duration]
    run(*cmd, '-map', '0:v:0', '-map', '0:a:0?', '-vf', ','.join(filters), '-c:v', 'libx264', '-crf', 16,
        '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', source)
    normalized = probe(source)
    v = next(s for s in normalized['streams'] if s['codec_type'] == 'video')
    w, h, count = int(v['width']), int(v['height']), int(v['nb_frames'])
    masks = a.mask_dir or a.output/'masks'
    if not a.mask_dir:
        cache = a.output/'swift-cache'
        cache.mkdir()
        run('swift', '-module-cache-path', cache, HERE/'video_masks.swift', source, masks, w, h)
    files = sorted(masks.glob('*.png'))
    if [x.name for x in files] != [f'{i:06d}.png' for i in range(count)]:
        raise ValueError('Masks must be 000000.png onward, one per normalized frame')
    scale = min(w, h)/1080
    outline = Outline(w, h, a.stroke*scale, a.offset*scale, a.jitter*scale)
    capture = cv2.VideoCapture(str(source))
    result = a.output/'preview.mp4'
    encoder = subprocess.Popen(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-nostdin', '-f', 'rawvideo',
        '-pix_fmt', 'bgr24', '-s', f'{w}x{h}', '-r', str(fps), '-i', '-', '-i', str(source),
        '-map', '0:v:0', '-map', '1:a:0?', '-c:v', 'libx264', '-preset', 'medium', '-crf', '17',
        '-pix_fmt', 'yuv420p', '-c:a', 'copy', '-movflags', '+faststart', str(result)], stdin=subprocess.PIPE)
    missing, ambiguous, frames, samples = [], [], 0, []
    try:
        for i, path in enumerate(files):
            ok, frame = capture.read()
            if not ok:
                raise ValueError(f'Video decode ended at frame {i}')
            mask = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
            if mask is None or mask.shape != (h, w):
                raise ValueError(f'Invalid mask dimensions: {path}')
            alpha, area, multiple = outline.draw(mask, i/float(fps))
            if not area:
                missing.append(i)
            if multiple:
                ambiguous.append(i)
            blended = np.rint(frame.astype(float)*(1-alpha[..., None]/255) + alpha[..., None]).astype(np.uint8)
            encoder.stdin.write(blended.tobytes())
            frames += 1
            if i in {0, count//4, count//2, count*3//4, count-1}:
                thumb = cv2.resize(blended, (round(w*360/h), 360))
                cv2.putText(thumb, f'{i/float(fps):.2f}s', (12, 26), cv2.FONT_HERSHEY_SIMPLEX, .65, (0, 0, 0), 3)
                cv2.putText(thumb, f'{i/float(fps):.2f}s', (12, 26), cv2.FONT_HERSHEY_SIMPLEX, .65, (255, 255, 255), 1)
                samples.append(thumb)
            if i % 60 == 0:
                print(f'render {i}/{count}', flush=True)
    finally:
        capture.release()
        encoder.stdin.close()
        status = encoder.wait()
    if status or frames != count:
        raise RuntimeError('Render incomplete')
    if samples:
        cv2.imwrite(str(a.output/'contact-sheet.jpg'), np.concatenate(samples, axis=1))
    out = probe(result)
    ov = next(s for s in out['streams'] if s['codec_type'] == 'video')
    assert int(ov['nb_frames']) == count, 'Output frame mismatch'
    has_audio = any(s['codec_type'] == 'audio' for s in normalized['streams'])
    assert has_audio == any(s['codec_type'] == 'audio' for s in out['streams']), 'Audio missing'
    report = {'input': str(a.video.resolve()), 'frames': count, 'fps': str(fps), 'width': w, 'height': h,
              'audio_preserved': has_audio, 'missing_person_frames': missing,
              'ambiguous_component_frames': ambiguous, 'settings': {'stroke': a.stroke, 'offset': a.offset, 'jitter': a.jitter},
              'review_required': 'Inspect playback for edge stability, occlusions and subject switches; largest connected person region only.'}
    (a.output/'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps({'preview': str(result), 'frames': count, 'missing': len(missing), 'ambiguous': len(ambiguous)}))


if __name__ == '__main__':
    main()
