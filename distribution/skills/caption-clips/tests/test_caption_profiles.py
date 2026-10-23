import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from caption_profiles import build_profile_manifest,load_profile,validate_profile_manifest,wrap_two_lines
from premiere_native_cards import load, payload, pool
from native_graphics.decode_graphic_text import decode_runs

WORDS=[
    {"word":"you","start":0.0,"end":0.2,"source_indices":[0]},
    {"word":"have","start":0.2,"end":0.4,"source_indices":[1]},
    {"word":"to","start":0.4,"end":0.55,"source_indices":[2]},
    {"word":"trust","start":0.55,"end":0.8,"source_indices":[3]},
    {"word":"yourself.","start":0.8,"end":1.15,"source_indices":[4],"sentence_end":True},
]

def test_profile_default_and_ids():
    assert load_profile(None)["id"]=="alex"
    assert load_profile("leila")["max_lines"]==2
    assert load_profile("sharran")["allow_weight_variation"] is False
    assert load_profile("sharran")["font_size_px"]==48
    assert load_profile("sharran")["max_chars_per_line"]==23
    assert load_profile("sharran")["reveal_mode"]=="adaptive"
    assert load_profile("sharran")["italic_font_postscript"]=="Inter-SemiBold"
    assert load_profile("sharran")["shadow_profile"]=="official-premiere-preset"
    assert load_profile("leila")["font_size_px"]==48
    assert load_profile("leila")["allow_weight_variation"] is False
    assert load_profile("leila")["shadow_profile"]=="official-premiere-preset"
    assert load_profile("leila")["body_font_postscript"]=="ClashGroteskVariable-Regular"
    assert load_profile("leila")["italic_font_postscript"]=="ClashGroteskVariable-Regular"
    assert load_profile("leila")["max_chars_per_line"]==23
    assert load_profile("leila")["min_words_per_card"]==4
    assert load_profile("leila")["max_words_per_card"]==10
    assert load_profile("leila")["max_words_per_quote_card"]==8
    assert load_profile("sharran")["max_text_width_pct"]==80

def test_approved_leila_assets_are_exact_and_self_contained():
    profile=load_profile("leila")
    font=ROOT/profile["vendored_font"]
    preset=ROOT/profile["premiere_text_style_preset"]
    assert font.is_file() and preset.is_file()
    root=load(preset); shared=pool(root); runs=[]
    for node in root.iter("StartKeyframeValue"):
        try:
            runs.extend(decode_runs(payload(node,shared)))
        except Exception:
            continue
    exact=[r for r in runs if r.get("font_postscript")==profile["body_font_postscript"]]
    assert len(exact)==1
    assert exact[0]["font_size_raw"]==48.0
    assert exact[0]["synthetic_italic_raw"] in (None,0)

def test_two_line_wrap_is_explicit():
    text,lines=wrap_two_lines(["Communication","builds","real","trust"],18)
    assert text=="\n".join(lines) and len(lines)==2
    assert all(len(line)<=18 for line in lines)

def test_leila_defaults_to_complete_phrase_card():
    data=build_profile_manifest(WORDS,load_profile("leila"))
    validate_profile_manifest(data)
    segs=data["render_segments"]
    assert [len(s["words"]) for s in segs]==[5]
    assert segs[0]["animation_elapsed_frames"]==0
    assert sum(bool(s["source_coverage_owner"]) for s in segs)==1
    assert segs[-1]["text"].replace("\n"," ")=="You have to trust yourself"
    assert len(segs[-1]["lines"])==2

def test_leila_slow_two_line_delivery_reveals_by_line_not_word():
    slow=[dict(w) for w in WORDS]
    for i,row in enumerate(slow):
        row["start"]=i*0.45; row["end"]=i*0.45+0.25
    data=build_profile_manifest(slow,load_profile("leila"))
    validate_profile_manifest(data)
    assert [len(s["words"]) for s in data["render_segments"]]==[3,5]
    assert data["render_segments"][1]["continuation"]
    assert data["render_segments"][1]["animation_elapsed_frames"]>0

def test_leila_word_reveal_requires_reviewed_override():
    reviewed=[dict(w, reveal_mode="word") for w in WORDS]
    data=build_profile_manifest(reviewed,load_profile("leila"))
    validate_profile_manifest(data)
    assert [len(s["words"]) for s in data["render_segments"]]==[1,2,3,4,5]

def test_sharran_is_uniform_inter_semibold():
    data=build_profile_manifest(WORDS,load_profile("sharran"))
    validate_profile_manifest(data)
    assert all(w["font_postscript"]=="Inter-SemiBold" and not w["italic"]
               for seg in data["render_segments"] for w in seg["words"])
    assert data["style_review"]["mode"]=="uniform_requested"
    assert len(data["render_segments"])==len(data["cards"])

def test_sharran_uses_reviewed_leila_line_reveal_logic_without_font_variation():
    plan=[
        {"first":0,"last":2,"lines":["You have to"],"reveal":"full_card"},
        {"first":3,"last":4,"lines":["trust","yourself"],"reveal":"line"},
    ]
    data=build_profile_manifest(WORDS,load_profile("sharran"),reviewed_plan=plan)
    validate_profile_manifest(data)
    assert [len(s["words"]) for s in data["render_segments"]]==[3,1,2]
    assert all(w["font_postscript"]=="Inter-SemiBold"
               for seg in data["render_segments"] for w in seg["words"])

def test_clean_punctuation_keeps_quotes_questions_and_numeric_marks():
    words=[
        {"word":"Well,","start":0.0,"end":0.2,"source_indices":[0]},
        {"word":"Acquisition.com.","start":0.2,"end":0.4,"source_indices":[1]},
        {"word":"asked:","start":0.4,"end":0.6,"source_indices":[2]},
        {"word":"\"Why?\"","start":0.6,"end":0.9,"source_indices":[3],"sentence_end":True},
    ]
    data=build_profile_manifest(words,load_profile("leila"))
    text=" ".join(c["text"].replace("\n"," ") for c in data["cards"])
    assert text=='Well Acquisition.com. Asked "Why?"'

def test_both_profiles_keep_quote_marks_and_use_quote_italics():
    quoted=[
        {"word":"She","start":0.0,"end":0.2,"source_indices":[0]},
        {"word":"said","start":0.2,"end":0.4,"source_indices":[1]},
        {"word":"\"do","start":0.4,"end":0.6,"source_indices":[2]},
        {"word":"it,","start":0.6,"end":0.8,"source_indices":[3]},
        {"word":"now.\"","start":0.8,"end":1.0,"source_indices":[4],"sentence_end":True},
    ]
    for profile_id in ("leila","sharran"):
        data=build_profile_manifest(quoted,load_profile(profile_id))
        words=[w for card in data["cards"] for w in card["words"]]
        assert [w["text"].strip('"') for w in words][-3:]==['do','it','now']
        assert all(w["italic"] for w in words[-3:])
        assert not any(w["italic"] for w in words[:2])
        quote_cards=[c for c in data["cards"] if all(w["italic"] for w in c["words"])]
        assert quote_cards and all(c["text"].startswith('"') and c["text"].endswith('"') for c in quote_cards)
        validate_profile_manifest(data)

def test_profile_manifest_roundtrip_json():
    data=build_profile_manifest(WORDS,load_profile("leila"))
    validate_profile_manifest(json.loads(json.dumps(data)))
    assert all(s["font_size_px"]==48 and s["max_text_width_pct"]==80
               for s in data["render_segments"])

def test_leila_size_calibration_does_not_leak_to_sharran():
    data=build_profile_manifest(WORDS,load_profile("sharran"))
    assert all(s["font_size_px"]==48 and s["max_text_width_pct"]==80
               for s in data["render_segments"])

def test_leila_has_no_bold_emphasis_variation():
    stressed=[dict(w, emphasis=True) for w in WORDS]
    data=build_profile_manifest(stressed,load_profile("leila"))
    assert all(w["weight"]=="base" and w["font_postscript"]=="ClashGroteskVariable-Regular"
               for seg in data["render_segments"] for w in seg["words"])

def test_reviewed_plan_locks_semantic_cards_lines_and_reveal():
    plan=[
        {"first":0,"last":2,"lines":["You have to"],"reveal":"full_card"},
        {"first":3,"last":4,"lines":["trust","yourself"],"reveal":"line"},
    ]
    data=build_profile_manifest(WORDS,load_profile("leila"),reviewed_plan=plan)
    validate_profile_manifest(data)
    assert [c["lines"] for c in data["cards"]]==[["You have to"],["trust","yourself"]]
    assert [len(s["words"]) for s in data["render_segments"]]==[3,1,2]
    assert data["render_segments"][-1]["continuation"]

def test_reviewed_plan_requires_exact_source_coverage():
    try:
        build_profile_manifest(WORDS,load_profile("leila"),reviewed_plan=[
            {"first":1,"last":4,"lines":["Have to trust","yourself"],"reveal":"full_card"}
        ])
    except ValueError as exc:
        assert "exact source coverage" in str(exc)
    else:
        raise AssertionError("gapped reviewed plan should fail")
