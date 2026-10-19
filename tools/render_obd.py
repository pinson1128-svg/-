#!/usr/bin/env python3
"""Edit the user's OBD installation footage without color or exposure filters."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile

CUTS = [
    (46.8, 49.4, 'PARKED. STILL RECORDING?', 'OBD power for parking monitoring.'),
    (0.0, 2.8, 'THE OBD POWER CABLE', 'Use a compatible cable for your dash cam.'),
    (10.5, 15.5, '01 / CONNECT THE ADAPTER', 'Plug it into the OBD-II port beneath the dash.'),
    (18.0, 20.0, '02 / CONNECT THE CAMERA', 'Take the power lead to your dash cam.'),
    (24.0, 28.0, '02 / CONNECT THE CAMERA', 'Connect the lead to the camera power input.'),
    (29.0, 34.5, '03 / CHECK POWER', 'Confirm that the dash cam powers on.'),
    (43.0, 50.8, '04 / CHECK WHILE PARKED', 'With the ignition off, check that recording stays active.\nParking mode depends on camera and vehicle compatibility.'),
]

def run(args, **kwargs):
    subprocess.run([str(arg) for arg in args], check=True, **kwargs)

def stamp(t, ass=False):
    ms = round(t * 1000)
    if ass:
        return f'{ms//3600000}:{ms//60000%60:02}:{ms//1000%60:02}.{ms//10%100:02}'
    return f'{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02},{ms%1000:03}'

def render(source, output):
    output.mkdir(parents=True, exist_ok=True)
    probe = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(source)]))
    video = next(s for s in probe['streams'] if s['codec_type'] == 'video')
    if (video['width'], video['height'], video.get('color_transfer')) != (720, 1280, 'bt709'):
        raise ValueError('This edit is for the supplied 720x1280 SDR BT.709 source; inspect a different source first.')
    if float(probe['format']['duration']) < max(end for _, end, _, _ in CUTS):
        raise ValueError('Source is shorter than the edit plan')
    with tempfile.TemporaryDirectory(prefix='obd-us-') as folder:
        folder = Path(folder)
        cursor, srt, events, clips = 0.0, [], [], []
        for i, (start, end, heading, text) in enumerate(CUTS):
            length = end - start
            clip = folder / f'clip{i}.mp4'
            # Native size, orientation, frame rate and original audio. No color filters.
            run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-ss', start, '-i', source,
                 '-t', length, '-map', '0:v:0', '-map', '0:a:0', '-c:v', 'libx264',
                 '-preset', 'fast', '-crf', '17', '-threads', '2', '-pix_fmt', 'yuv420p',
                 '-af', f'apad,atrim=duration={length},afade=t=in:d=0.015,afade=t=out:st={length-0.015}:d=0.015',
                 '-c:a', 'aac', '-b:a', '128k', '-ar', '48000', '-ac', '2',
                 '-color_primaries', 'bt709', '-color_trc', 'bt709', '-colorspace', 'bt709',
                 '-map_metadata', '-1', clip])
            clips.append(clip)
            end_time = cursor + length
            srt.append(f'{i+1}\n{stamp(cursor)} --> {stamp(end_time)}\n{text}')
            for style, content in [('Heading', heading), ('Caption', text)]:
                content = content.replace('\n', r'\N')
                events.append(f'Dialogue: 0,{stamp(cursor,True)},{stamp(end_time,True)},{style},,0,0,0,,{{\\fad(100,100)}}{content}')
            cursor = end_time
        header = '''[Script Info]
ScriptType: v4.00+
PlayResX: 720
PlayResY: 1280
WrapStyle: 0
ScaledBorderAndShadow: yes
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Heading,DejaVu Sans,31,&H00FFFFFF,&H00FFFFFF,&H00222222,&H80000000,-1,0,0,0,100,100,0,0,1,2,1,8,42,42,125,1
Style: Caption,DejaVu Sans,32,&H00FFFFFF,&H00FFFFFF,&H00222222,&H80000000,-1,0,0,0,100,100,0,0,3,8,0,2,60,60,215,1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
'''
        (folder / 'captions.ass').write_text(header + '\n'.join(events) + '\n')
        (folder / 'clips.txt').write_text(''.join(f"file '{clip}'\n" for clip in clips))
        run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-f', 'concat', '-safe', '0',
             '-i', folder / 'clips.txt', '-c', 'copy', folder / 'joined.mp4'])
        run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-i', folder / 'joined.mp4',
             '-vf', 'ass=captions.ass', '-c:v', 'libx264', '-preset', 'fast', '-crf', '17',
             '-threads', '2', '-c:a', 'copy', '-pix_fmt', 'yuv420p', '-color_primaries', 'bt709',
             '-color_trc', 'bt709', '-colorspace', 'bt709', '-map_metadata', '-1',
             '-movflags', '+faststart', output / 'en.mp4'], cwd=folder)
        (output / 'en.srt').write_text('\n\n'.join(srt) + '\n')
        (output / 'edit-plan.json').write_text(json.dumps({'cuts': CUTS, 'duration': cursor,
            'color_processing': 'none', 'audio': 'original source audio; no synthesized narration'}, indent=2))
        print(f'English OBD installation edit: {cursor:.2f}s', flush=True)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    render(args.source.resolve(), args.output.resolve())
