"""Generate several ACE-Step 1.5 clips with one model load (optional; needs the ace-step install + NVIDIA GPU).

    E:\\YT_Longform_Music\\ace-step\\.venv\\Scripts\\python tools\\ace_batch.py tools\\ace_batches\\piano_round2.json

The JSON has shared settings plus a list of variants; each variant overrides any shared key:
    {"model": "acestep-v15-turbo", "lm": null, "seconds": 120, "prompt": "...",
     "variants": [{"name": "a", "seed": 21}, {"name": "b", "seed": 22, "thinking": true}]}
"lm" names a language model (e.g. "acestep-5Hz-lm-1.7B") to load for variants with "thinking": true.
Clips land in $SLEEPGEN_OUTPUT/ace (or ./output/ace), each with a JSON of its settings.
"""
import json
import os
import shutil
import sys
from pathlib import Path

ACE_ROOT = Path(os.environ.get("ACESTEP_ROOT", r"E:\YT_Longform_Music\ace-step"))
PARAM_KEYS = {"seed", "bpm", "steps", "guidance", "thinking", "seconds", "prompt", "key"}


def main() -> None:
    batch_file = Path(sys.argv[1]).resolve()
    batch = json.loads(batch_file.read_text())
    out = Path(os.environ.get("SLEEPGEN_OUTPUT", Path(__file__).resolve().parents[1] / "output")) / "ace"
    out.mkdir(parents=True, exist_ok=True)

    os.chdir(ACE_ROOT)
    from acestep.handler import AceStepHandler
    from acestep.inference import GenerationConfig, GenerationParams, generate_music
    from acestep.llm_inference import LLMHandler

    dit = AceStepHandler()
    dit.initialize_service(project_root=str(ACE_ROOT), config_path=batch["model"], device="cuda")
    llm = None
    if batch.get("lm"):
        llm = LLMHandler()
        llm.initialize(checkpoint_dir=str(ACE_ROOT / "checkpoints"), lm_model_path=batch["lm"], backend="pt", device="cuda")

    shared = {k: v for k, v in batch.items() if k in PARAM_KEYS}
    for variant in batch["variants"]:
        s = {**shared, **variant}
        params = GenerationParams(
            caption=s["prompt"], lyrics="[Instrumental]", instrumental=True,
            duration=s.get("seconds", 120), bpm=s.get("bpm"), keyscale=s.get("key", ""),
            seed=s.get("seed", 21), inference_steps=s.get("steps", 8),
            guidance_scale=s.get("guidance", 7.0), thinking=bool(s.get("thinking", False)),
        )
        result = generate_music(dit, llm, params, GenerationConfig(batch_size=1, audio_format="wav"),
                                save_dir=str(ACE_ROOT / "_tmp_out"))
        if not result.success:
            print(f"FAILED {variant['name']}: {result.error}", flush=True)
            continue
        dst = out / f"{batch_file.stem}_{variant['name']}_{s.get('seed', 21)}.wav"
        shutil.move(result.audios[0]["path"], dst)
        dst.with_suffix(".json").write_text(json.dumps({"model": batch["model"], **s}, indent=2))
        print(f"saved {dst}", flush=True)


if __name__ == "__main__":
    main()
