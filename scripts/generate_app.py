import argparse
import json
import os
from pathlib import Path
from datetime import datetime

import yaml
from openai import OpenAI

PROMPT_TEMPLATE = """
You are an expert software architect and engineer. You will be given a YAML spec describing an application that should be built to solve a user problem. Return a JSON object with this shape:
{
  "files": [
    {
      "path": "relative/path/to/file",
      "content": "file contents"
    }
  ],
  "summary": "High level summary of what was generated.",
  "notes": "Any important follow-up notes or TODOs."
}

Guidelines:
- Generate production-ready starter code that satisfies the spec.
- Include README or usage notes inside the generated project if helpful.
- Favor lightweight dependencies and provide package configuration files when needed.
- Do not include markdown fences or extra commentary outside the JSON payload.
""".strip()


def load_spec(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fp:
        return yaml.safe_load(fp)


def build_prompt(spec: dict) -> str:
    spec_json = json.dumps(spec, ensure_ascii=False, indent=2)
    return f"{PROMPT_TEMPLATE}\n\nHere is the spec to fulfill:\n{spec_json}"


def ensure_output_dir(base_dir: Path, spec_id: str) -> Path:
    target = base_dir / spec_id
    target.mkdir(parents=True, exist_ok=True)
    return target


def write_files(target_dir: Path, files: list[dict]) -> None:
    for file_entry in files:
        rel_path = Path(file_entry["path"])
        full_path = target_dir / rel_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        content = file_entry["content"]
        full_path.write_text(content, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate an app from a human-authored spec using an LLM.")
    parser.add_argument("spec_path", help="Path to the YAML spec file.")
    parser.add_argument("--output-dir", default="generated_apps", help="Directory where generated apps are stored.")
    parser.add_argument("--model", default=os.getenv("GENERATOR_MODEL", "gpt-4o-mini"), help="LLM model identifier.")
    args = parser.parse_args()

    spec_path = Path(args.spec_path)
    if not spec_path.exists():
        raise FileNotFoundError(f"Spec file not found: {spec_path}")

    spec = load_spec(spec_path)
    spec_id = spec.get("id")
    if not spec_id:
        raise ValueError("Spec must include an 'id' field.")

    if not spec.get("auto_generate", True):
        raise ValueError("Spec is marked with auto_generate: false. Enable it to run generation.")

    client = OpenAI()
    prompt = build_prompt(spec)

    response = client.responses.create(
        model=args.model,
        input=[
            {
                "role": "system",
                "content": [
                    {
                        "type": "text",
                        "text": "You translate specs into working application skeletons. Output only valid JSON as requested."
                    }
                ],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt,
                    }
                ],
            },
        ],
    )

    output_text = response.output_text
    data = json.loads(output_text)

    files = data.get("files", [])
    if not files:
        raise ValueError("LLM response did not include any files to write.")

    output_dir = ensure_output_dir(Path(args.output_dir), spec_id)
    write_files(output_dir, files)

    metadata = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "model": args.model,
        "summary": data.get("summary", ""),
        "notes": data.get("notes", ""),
        "spec_path": str(spec_path),
    }
    (output_dir / "generation_metadata.json").write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    (output_dir / "source_spec.yaml").write_text(yaml.safe_dump(spec, sort_keys=False, allow_unicode=True), encoding="utf-8")

    print(f"App generated in {output_dir}")


if __name__ == "__main__":
    main()
