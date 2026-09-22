"""Course knowledge base for the DeepTutor course backend.

Chunks course.md into module-scoped sections and retrieves by keyword overlap.
Deliberately serverless-safe: no vector store, no on-disk state — everything is
parsed once per cold start from the bundled course file.
"""
import re
from pathlib import Path

_STOP = set("""a an and are as at be by for from how i in is it its of on or that the this to what when which who why with you your do does can""".split())

_HEAD_MOD = re.compile(r"^####\s+(M\d{2})\s*[·\.]\s*(.+?)\s*$")
_HEAD_PART = re.compile(r"^###\s+(Part\s+[IVX]+.*)$")
_HEAD_SEC = re.compile(r"^##\s+(\d\..*|Appendix.*)$")


class CourseKB:
    def __init__(self, path):
        self.path = Path(path)
        text = self.path.read_text(encoding="utf-8")
        self.chunks = []
        self._parse(text)

    def _parse(self, text):
        part, module, title, buf = "", "", "", []

        def flush():
            body = "\n".join(buf).strip()
            if not body:
                return
            self.chunks.append({
                "module": module or "GEN",
                "title": (title or part or "Course overview")[:90],
                "text": body[:4500],
            })

        for line in text.splitlines():
            m = _HEAD_MOD.match(line)
            p = _HEAD_PART.match(line)
            s = _HEAD_SEC.match(line)
            if m:
                flush()
                buf = []
                module, title = m.group(1), m.group(2)
            elif p:
                flush()
                buf = [line]
                part, module, title = p.group(1), "", p.group(1)
            elif s:
                flush()
                buf = [line]
                module, title = "GEN", s.group(1)
            else:
                if line.strip().startswith("#") or line.strip() == "---":
                    continue
                buf.append(line)
        flush()

    @property
    def modules(self):
        seen = []
        for c in self.chunks:
            if c["module"].startswith("M") and (not seen or seen[-1][0] != c["module"]):
                seen.append((c["module"], c["title"]))
        return [{"module": m, "title": t} for m, t in seen]

    def retrieve(self, query, module=None, k=4):
        terms = [t for t in re.split(r"[^a-z0-9]+", query.lower()) if len(t) > 2 and t not in _STOP]
        scored = []
        for c in self.chunks:
            text = c["text"].lower()
            title = c["title"].lower()
            score = sum(3 if t in title else 0 for t in terms)
            score += sum(1 for t in terms if t in text)
            if module and c["module"] == module:
                score += 6
            if score > 0:
                scored.append((score, c))
        scored.sort(key=lambda x: -x[0])
        return [c for _, c in scored[:k]]
