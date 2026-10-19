"""Generate instrumental clips with ACE-Step 1.5 (optional; needs the ace-step install and an NVIDIA GPU).

Run with ACE-Step's own Python, from anywhere:
    E:\\YT_Longform_Music\\ace-step\\.venv\\Scripts\\python tools\\ace_generate.py --prompt "soft felt piano" --seconds 120

Clips are saved to $SLEEPGEN_OUTPUT/ace (or ./output/ace) with a JSON of the prompt and seed.
"""
import argparse
import json
import os
import shutil
from pathlib import Path

ACE_ROOT = Path(os.environ.get("ACESTEP_ROOT", r"E:\YT_Longform_Music\ace-step"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", required=True, help="caption describing the sound")
    ap.add_argument("--seconds", type=float, default=120)
    ap.add_argument("--seed", type=int, default=21)
    ap.add_argument("--bpm", type=int)
    ap.add_argument("--key", default="", help='for example "C minor"')
    ap.add_argument("--model", default="acestep-v15-turbo")
    ap.add_argument("--steps", type=int, default=8)
    ap.add_argument("--name", required=True, help="file name stem")
    args = ap.parse_args()

    os.chdir(ACE_ROOT)
    from acestep.handler import AceStepHandler
    from acestep.inference import GenerationConfig, GenerationParams, generate_music

    dit = AceStepHandler()
    dit.initialize_service(project_root=str(ACE_ROOT), config_path=args.model, device="cuda")

    params = GenerationParams(
        caption=args.prompt, lyrics="[Instrumental]", instrumental=True,
        duration=args.seconds, bpm=args.bpm, keyscale=args.key,
        seed=args.seed, inference_steps=args.steps, thinking=False,
    )
    out = Path(os.environ.get("SLEEPGEN_OUTPUT", Path(__file__).resolve().parents[1] / "output")) / "ace"
    out.mkdir(parents=True, exist_ok=True)
    tmp = ACE_ROOT / "_tmp_out"
    result = generate_music(dit, None, params, GenerationConfig(batch_size=1, audio_format="wav"), save_dir=str(tmp))
    if not result.success:
        raise SystemExit(f"generation failed: {result.error}")
    src = Path(result.audios[0]["path"])
    dst = out / f"{args.name}_{args.seed}{src.suffix}"
    shutil.move(src, dst)
    meta = {k: v for k, v in vars(args).items()}
    dst.with_suffix(".json").write_text(json.dumps(meta, indent=2))
    print(f"saved {dst}")


if __name__ == "__main__":
    main()
