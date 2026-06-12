#!/usr/bin/env python3
"""
agent_analysis.py — Multi-Agent Scene Analyzer (using agy CLI)
Processes the docx manuscript, hashes scene contents to detect edits,
and orchestrates the scene-by-scene analysis.
"""

import os
import sys
import json
import hashlib
import subprocess
from pathlib import Path
from datetime import datetime

# Import parsing logic from build.py
sys.path.append(str(Path(__file__).parent))
try:
    import build
except ImportError:
    print("ERROR: Could not import build.py. Make sure this script is run inside the repository root.")
    sys.exit(1)

OUT_DIR = Path(__file__).parent
ANALYSIS_DIR = OUT_DIR / "analysis"
CACHE_FILE = ANALYSIS_DIR / "cache_manifest.json"

def get_scene_hash(text):
    """Return MD5 hash of the scene text for change detection."""
    return hashlib.md5(text.encode('utf-8')).hexdigest()

def clean_json_output(stdout_text):
    """Extract and parse the JSON block from agy's output."""
    start = stdout_text.find('{')
    end = stdout_text.rfind('}')
    if start == -1 or end == -1:
        raise ValueError("No JSON object found in CLI response.")
    
    json_str = stdout_text[start:end+1]
    
    # Try parsing directly
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        # Attempt to clean up common formatting anomalies (like trailing commas before braces)
        # We can try simple regex/replacements
        import re
        # Remove trailing commas from objects/arrays
        cleaned = re.sub(r',\s*([\]}])', r'\1', json_str)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            # Save raw to a debug file and raise
            debug_path = OUT_DIR / "analysis_error_debug.txt"
            debug_path.write_text(stdout_text, encoding='utf-8')
            raise ValueError(f"JSON parsing failed: {e}. Raw output saved to analysis_error_debug.txt")

def analyze_scene(ch_num, ch_title, scene_num, scene_heading, scene_text):
    """Invoke the agy CLI in print mode to analyze a single scene."""
    prompt = (
        f"Here is a scene from the novel 'String Theory' by Gabriel McPherson.\n"
        f"Chapter Label: Chapter {ch_num}\n"
        f"Chapter Title: {ch_title}\n"
        f"Scene Number: {scene_num}\n"
        f"Scene Heading: {scene_heading}\n\n"
        f"Scene Text:\n{scene_text}\n\n"
        f"Please analyze this scene and provide:\n"
        f"1. A narrative summary (brief overview of the scene's plot).\n"
        f"2. A detailed beat-by-beat scene outline (a bulleted list of 3-7 concrete actions/plot beats that happen in the scene).\n"
        f"3. A narrative and thematic analysis (character motivations, subtext, motifs, and musical/resonance elements).\n\n"
        f"Your output MUST be a single raw JSON object matching the following structure exactly (do not output any markdown formatting, backticks, thoughts, or text outside the JSON, just the raw JSON object):\n"
        f'{{\n  "summary": "narrative summary here",\n  "outline": ["beat 1", "beat 2", "beat 3"],\n  "analysis": "thematic analysis here"\n}}'
    )
    
    # Run agy non-interactively
    cmd = [
        "agy",
        "--dangerously-skip-permissions",
        "-p",
        prompt
    ]
    
    print(f"  --> Calling agy to analyze Chapter {ch_num}, Scene {scene_num}...", flush=True)
    res = subprocess.run(cmd, capture_output=True, text=True)
    
    if res.returncode != 0:
        print(f"  ERROR: agy exited with code {res.returncode}", file=sys.stderr)
        if res.stderr:
            print(f"  STDERR: {res.stderr}", file=sys.stderr)
        raise RuntimeError(f"agy CLI run failed.")
        
    return clean_json_output(res.stdout)

def main():
    # Find latest DOCX
    src_path = build.DEFAULT_SRC
    if not src_path.exists():
        candidates = sorted(build.GDRIVE.glob("*.docx"),
                            key=lambda f: f.stat().st_mtime, reverse=True)
        if not candidates:
            print(f"ERROR: No DOCX found in {build.GDRIVE}")
            sys.exit(1)
        src_path = candidates[0]
        
    print(f"Loading manuscript for scene analysis: {src_path.name}")
    
    # Initialize directory
    ANALYSIS_DIR.mkdir(exist_ok=True)
    
    # Load cache
    cache = {}
    if CACHE_FILE.exists():
        try:
            cache = json.loads(CACHE_FILE.read_text(encoding='utf-8'))
        except Exception as e:
            print(f"Warning: Failed to load cache manifest: {e}. Re-analyzing all scenes.")

    # Parse chapters using build.py
    chapters = build.parse_chapters(src_path)
    
    # Track statistics
    total_scenes_processed = 0
    scenes_analyzed_count = 0
    
    for num, paras in chapters:
        ch_title, _, _ = build.extract_meta(paras)
        body_paras = build.strip_header_paras(paras)
        scenes_grouped = build.extract_scenes(body_paras)
        
        ch_slug = build.slugify(num)
        
        for sg in scenes_grouped:
            sc_n = sg['n']
            scene_heading = sg['heading']
            
            # Reconstruct scene text
            scene_text = "\n".join(p.text for p in sg['paras'] if p.text.strip())
            
            scene_id = f"{ch_slug}-scene-{sc_n:02d}"
            scene_hash = get_scene_hash(scene_text)
            
            out_file = ANALYSIS_DIR / f"{scene_id}.json"
            
            # Check if cache is hit
            if scene_id in cache and cache[scene_id].get("hash") == scene_hash and out_file.exists():
                # Cache hit
                total_scenes_processed += 1
                continue
                
            # Cache miss or file missing -> Analyze
            print(f"Analyzing {scene_id} ({scene_heading[:30]}...)", flush=True)
            try:
                analysis_data = analyze_scene(num, ch_title, sc_n, scene_heading, scene_text)
                
                # Save to JSON
                out_file.write_text(json.dumps(analysis_data, indent=2, ensure_ascii=False), encoding='utf-8')
                
                # Update cache entry
                cache[scene_id] = {
                    "hash": scene_hash,
                    "file": f"analysis/{scene_id}.json",
                    "heading": scene_heading,
                    "analyzed_at": datetime.now().isoformat()
                }
                
                scenes_analyzed_count += 1
                total_scenes_processed += 1
                
                # Save cache manifest progressively in case script gets interrupted
                CACHE_FILE.write_text(json.dumps(cache, indent=2, ensure_ascii=False), encoding='utf-8')
                
            except Exception as e:
                print(f"  Failed to analyze scene {scene_id}: {e}", file=sys.stderr)
                # Continue with next scenes but exit with warning/non-zero later
                
    # Save cache manifest final
    CACHE_FILE.write_text(json.dumps(cache, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f"\nAnalysis complete. Processed {total_scenes_processed} scenes total. Newly analyzed: {scenes_analyzed_count}.")

if __name__ == "__main__":
    main()
