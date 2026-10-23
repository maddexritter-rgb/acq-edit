"""audio_mix — lay a music bed under a (silent) video and loudnorm the result.

Built for the anthropic-demo pipeline (no VO, no SFX — music is the only audio).

Config (manifest.stages.audio_mix):
    music:        project-relative path to the chosen track ("" = not yet chosen →
                  passthrough with silent audio; loudness QC will rightly fail, so
                  an unmixed cut can never ship by accident)
    loudnorm:     {i, tp, lra} target (e.g. -16 / -1.0 / 11)
    fade_out:     {start_s, end_s} linear music fade at the tail

Video stream is stream-copied (encoded upstream via fast_encode/VideoToolbox).
"""
import subprocess
from pathlib import Path

VERSION = "1"


def run(work_dir, config, inputs, inputs_meta, project, manifest, out_path):
    video = inputs["remotion_render"]
    vmeta = inputs_meta.get("remotion_render", {}) or {}
    dur = float(vmeta.get("duration_s") or 0)
    music = (config.get("music") or "").strip()

    if not music:
        # No track chosen yet — mux a silent bed so downstream probes see audio.
        cmd = [
            "ffmpeg", "-y", "-i", str(video),
            "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
            "-shortest", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", str(out_path),
        ]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(f"silent mux failed:\n{r.stderr[-2000:]}")
        return {"out": str(out_path), "meta": {"music": None, "silent": True}}

    mpath = Path(music)
    if not mpath.is_absolute():
        mpath = Path(project) / music
    if not mpath.exists():
        raise RuntimeError(f"music track not found: {mpath}")

    ln = config.get("loudnorm", {})
    i, tp, lra = ln.get("i", -16.0), ln.get("tp", -1.0), ln.get("lra", 11)
    fade = config.get("fade_out", {})
    af = [f"loudnorm=I={i}:TP={tp}:LRA={lra}"]
    if fade:
        fs, fe = float(fade["start_s"]), float(fade["end_s"])
        af.append(f"afade=t=out:st={fs}:d={fe - fs}")

    cmd = [
        "ffmpeg", "-y", "-i", str(video), "-i", str(mpath),
        "-filter_complex", f"[1:a]{','.join(af)}[a]",
        "-map", "0:v", "-map", "[a]",
        "-t", f"{dur:.3f}" if dur else "87",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", str(out_path),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"audio mix failed:\n{r.stderr[-2000:]}")
    return {"out": str(out_path), "meta": {"music": str(mpath), "silent": False,
                                           "loudnorm": {"i": i, "tp": tp, "lra": lra}}}
