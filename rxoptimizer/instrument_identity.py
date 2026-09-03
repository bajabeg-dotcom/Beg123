"""Canonical GM/Factory/RX instrument identities and strict conversion guards."""

from __future__ import annotations

import re


GM_PROGRAM_NAMES=(
"Acoustic Grand Piano","Bright Acoustic Piano","Electric Grand Piano","Honky-tonk Piano","Electric Piano 1","Electric Piano 2","Harpsichord","Clavinet",
"Celesta","Glockenspiel","Music Box","Vibraphone","Marimba","Xylophone","Tubular Bells","Dulcimer",
"Drawbar Organ","Percussive Organ","Rock Organ","Church Organ","Reed Organ","Accordion","Harmonica","Tango Accordion",
"Acoustic Guitar Nylon","Acoustic Guitar Steel","Electric Guitar Jazz","Electric Guitar Clean","Electric Guitar Muted","Overdriven Guitar","Distortion Guitar","Guitar Harmonics",
"Acoustic Bass","Finger Bass","Picked Bass","Fretless Bass","Slap Bass 1","Slap Bass 2","Synth Bass 1","Synth Bass 2",
"Violin","Viola","Cello","Contrabass","Tremolo Strings","Pizzicato Strings","Orchestral Harp","Timpani",
"String Ensemble 1","String Ensemble 2","Synth Strings 1","Synth Strings 2","Choir Aahs","Voice Oohs","Synth Voice","Orchestra Hit",
"Trumpet","Trombone","Tuba","Muted Trumpet","French Horn","Brass Section","Synth Brass 1","Synth Brass 2",
"Soprano Sax","Alto Sax","Tenor Sax","Baritone Sax","Oboe","English Horn","Bassoon","Clarinet",
"Piccolo","Flute","Recorder","Pan Flute","Blown Bottle","Shakuhachi","Whistle","Ocarina",
"Lead 1 Square","Lead 2 Sawtooth","Lead 3 Calliope","Lead 4 Chiff","Lead 5 Charang","Lead 6 Voice","Lead 7 Fifths","Lead 8 Bass Lead",
"Pad 1 New Age","Pad 2 Warm","Pad 3 Polysynth","Pad 4 Choir","Pad 5 Bowed","Pad 6 Metallic","Pad 7 Halo","Pad 8 Sweep",
"FX 1 Rain","FX 2 Soundtrack","FX 3 Crystal","FX 4 Atmosphere","FX 5 Brightness","FX 6 Goblins","FX 7 Echoes","FX 8 Sci-Fi",
"Sitar","Banjo","Shamisen","Koto","Kalimba","Bag Pipe","Fiddle","Shanai",
"Tinkle Bell","Agogo","Steel Drums","Woodblock","Taiko Drum","Melodic Tom","Synth Drum","Reverse Cymbal",
"Guitar Fret Noise","Breath Noise","Seashore","Bird Tweet","Telephone Ring","Helicopter","Applause","Gunshot")

FAMILIES=("piano","chromatic_percussion","organ","guitar","bass","strings","ensemble","brass",
          "reed","pipe","synth_lead","synth_pad","synth_fx","ethnic","percussive","sound_fx")


def slug(value: str) -> str:
    return "_".join(re.findall(r"[a-z0-9]+",value.casefold().replace("acous.","acoustic")))


def gm_family(program: int) -> str:
    return FAMILIES[max(0,min(127,int(program)))//8]


def gm_identity(program: int) -> str:
    return slug(GM_PROGRAM_NAMES[max(0,min(127,int(program)))])


def canonical_identity(program: int,name: str="",role: str="") -> str:
    text=slug(name).replace("_rx","").replace("_gm","")
    explicit=(
        (("slapfing","slap_fing","slap_finger"),"slap_finger_bass"),
        (("slappick","slap_pick"),"slap_pick_bass"),
        (("funk_slap","funkslap"),"funk_slap_bass"),
        (("finger_bass",),"finger_bass"),(("picked_bass","pick_bass"),"picked_bass"),
        (("acoustic_bass","acous_bass"),"acoustic_bass"),(("fretless_bass",),"fretless_bass"),
        (("clean_guitar","clean_gt","electric_guitar_clean"),"electric_guitar_clean"),
        (("steel_guitar",),"acoustic_guitar_steel"),(("nylon_guitar",),"acoustic_guitar_nylon"),
        (("jazz_guitar","jazz_gt"),"electric_guitar_jazz"),(("muted_guitar",),"electric_guitar_muted"),
        (("distortion_guitar","distort"),"distortion_guitar"),(("overdrive",),"overdriven_guitar"),
        (("pop_std_kit","pop_standard_kit"),"pop_standard_kit"),(("ambient_kit",),"ambient_kit"),
        (("jazz_kit",),"jazz_kit"),(("standard_kit",),"standard_kit"),
    )
    for tokens,identity in explicit:
        if any(token in text for token in tokens):return identity
    if role=="drums":return "standard_kit"
    if role=="percussion":return "percussion_kit"
    # GM Slap 1/2 are locked to the confirmed RX identities used by this project.
    if int(program)==36:return "funk_slap_bass"
    if int(program)==37:return "slap_pick_bass"
    return gm_identity(program)


def identity_family(identity: str,program: int=0) -> str:
    if identity.endswith("_kit") or "kit" in identity:return "drums"
    if "bass" in identity:return "bass"
    if "guitar" in identity:return "guitar"
    return gm_family(program)


def identities_compatible(source_program: int,source_name: str,target_program: int,target_name: str,
                          role: str="",same_address: bool=False) -> bool:
    if same_address:return True
    source=canonical_identity(source_program,source_name,role);target=canonical_identity(target_program,target_name,role)
    expected="drums" if role in ("drums","percussion") else role if role in ("bass","guitar") else None
    if expected and (identity_family(source,source_program)!=expected or identity_family(target,target_program)!=expected):return False
    return source==target