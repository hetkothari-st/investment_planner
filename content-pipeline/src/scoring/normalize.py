import re
import unicodedata

# English + common Hinglish stopwords. Deliberately small — normalization must be
# deterministic and idempotent, not linguistically perfect.
STOPWORDS = frozenset(
    """
    a an the and or but of in on at to for with from by is are was were be been
    this that these those it its as if so than then there here what which who
    how why when where all any not no do does did done have has had will would
    can could should just very over under again more most
    hai hain ka ki ke ko se me mein par aur ya nahi nahin kya kyu kyon bhi to
    ho hua hui gaya gayi wala wali vala vali
    """.split()
)

_NON_ALNUM = re.compile(r"[^a-z0-9\s]+")
_WS = re.compile(r"\s+")


def _light_stem(token: str) -> str:
    if len(token) > 4 and token.endswith("ies"):
        return token[:-3] + "y"
    if len(token) > 3 and token.endswith("es") and not token.endswith("ss"):
        return token[:-2]
    if len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


def normalize(topic: str) -> str:
    """lowercase -> strip punctuation/emoji -> remove stopwords -> light stem -> join with _

    Deterministic and idempotent: normalize(normalize(x)) == normalize(x).
    """
    text = unicodedata.normalize("NFKD", topic)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower().replace("_", " ")
    text = _NON_ALNUM.sub(" ", text)
    text = _WS.sub(" ", text).strip()
    tokens = [_light_stem(t) for t in text.split(" ") if t and t not in STOPWORDS]
    return "_".join(tokens)
