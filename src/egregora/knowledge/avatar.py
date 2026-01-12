"""Avatar generation tools."""

import hashlib

# Avatar generation constants
AVATAR_ACCESSORIES = ["Blank", "Kurt", "Prescription01", "Prescription02", "Round", "Sunglasses", "Wayfarers"]
AVATAR_CLOTHES = [
    "BlazerShirt",
    "BlazerSweater",
    "CollarSweater",
    "GraphicShirt",
    "Hoodie",
    "Overall",
    "ShirtCrewNeck",
    "ShirtScoopNeck",
    "ShirtVNeck",
]
AVATAR_EYES = [
    "Close",
    "Cry",
    "Default",
    "Dizzy",
    "EyeRoll",
    "Happy",
    "Hearts",
    "Side",
    "Squint",
    "Surprised",
    "Wink",
    "WinkWacky",
]
AVATAR_EYEBROWS = [
    "Angry",
    "AngryNatural",
    "Default",
    "DefaultNatural",
    "FlatNatural",
    "RaisedExcited",
    "RaisedExcitedNatural",
    "SadConcerned",
    "SadConcernedNatural",
    "UnibrowNatural",
    "UpDown",
    "UpDownNatural",
]
AVATAR_MOUTHS = [
    "Concerned",
    "Default",
    "Disbelief",
    "Eating",
    "Grimace",
    "Sad",
    "ScreamOpen",
    "Serious",
    "Smile",
    "Tongue",
    "Twinkle",
    "Vomit",
]
AVATAR_SKIN_COLORS = ["Tanned", "Yellow", "Pale", "Light", "Brown", "DarkBrown", "Black"]
AVATAR_TOPS = [
    "NoHair",
    "Eyepatch",
    "Hat",
    "Hijab",
    "Turban",
    "WinterHat1",
    "WinterHat2",
    "WinterHat3",
    "WinterHat4",
    "LongHairBigHair",
    "LongHairBob",
    "LongHairBun",
    "LongHairCurly",
    "LongHairCurvy",
    "LongHairDreads",
    "LongHairFrida",
    "LongHairFro",
    "LongHairFroBand",
    "LongHairNotTooLong",
    "LongHairShavedSides",
    "LongHairMiaWallace",
    "LongHairStraight",
    "LongHairStraight2",
    "LongHairStraightStrand",
    "ShortHairDreads01",
    "ShortHairDreads02",
    "ShortHairFrizzle",
    "ShortHairShaggyMullet",
    "ShortHairShortCurly",
    "ShortHairShortFlat",
    "ShortHairShortRound",
    "ShortHairShortWaved",
    "ShortHairSides",
    "ShortHairTheCaesar",
    "ShortHairTheCaesarSidePart",
]
AVATAR_HAIR_COLORS = [
    "Auburn",
    "Black",
    "Blonde",
    "BlondeGolden",
    "Brown",
    "BrownDark",
    "PastelPink",
    "Platinum",
    "Red",
    "SilverGray",
]


def generate_fallback_avatar_url(author_uuid: str) -> str:
    """Generate a deterministic fallback avatar URL using avataaars.io.

    Args:
        author_uuid: The author's UUID
    Returns:
        A URL to a generated avatar image.

    """
    # Deterministically select options based on UUID hash
    # We use different slices of the hash to pick different attributes
    h = hashlib.sha256(author_uuid.encode()).hexdigest()

    # Helper to pick from options
    def pick(options: list[str], offset: int) -> str:
        idx = int(h[offset : offset + 2], 16) % len(options)
        return options[idx]

    params = [
        f"accessoriesType={pick(AVATAR_ACCESSORIES, 0)}",
        "avatarStyle=Circle",
        f"clotheType={pick(AVATAR_CLOTHES, 2)}",
        f"eyeType={pick(AVATAR_EYES, 4)}",
        f"eyebrowType={pick(AVATAR_EYEBROWS, 6)}",
        "facialHairType=Blank",
        f"hairColor={pick(AVATAR_HAIR_COLORS, 8)}",
        f"mouthType={pick(AVATAR_MOUTHS, 10)}",
        f"skinColor={pick(AVATAR_SKIN_COLORS, 12)}",
        f"topType={pick(AVATAR_TOPS, 14)}",
    ]

    return f"https://avataaars.io/?{'&'.join(params)}"
