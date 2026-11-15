# Dictionary

A first-bite dictionary: the messages of one or more interfaces, transcribed
from an interface control document. The format is in
`docs/dictionary-format.md` of first-bite, and the way to fill this directory
in is `docs/icd-to-dictionary/`.

| Path | Holds |
|---|---|
| `dictionary.json` | the dictionary's name and version, the source document, and the findings it allows with a reason |
| `<INTERFACE>/metadata.json` | one interface: its port, how its messages are identified, the document's bit numbering |
| `<INTERFACE>/messages/<Message Name>.json` | one message: its fields, each a bit range `[start, stop)` |
| `vectors/<name>.json` | a payload and the values the document says it holds |

A dictionary transcribes its source document and is handled as that document
is. Keep it where the document may be kept.

Check it before every commit:

```bash
bite fmt --check .
bite check --strict .
bite lint .
bite coverage --strict .
```
