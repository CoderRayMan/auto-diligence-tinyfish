import sys; sys.path.insert(0, '.')
from src.utils.risk_scorer import _extract_penalty_from_text

tests = [
    ("Elon Musk agreed to pay $20 million penalty", 20_000_000),
    ("SEC charges Tesla, $20,000,000 disgorgement", 20_000_000),
    ("settlement of 40 million penalty resulting from", 40_000_000),
    ("no penalty mentioned", 0),
    ("$1.5 billion fine imposed", 1_500_000_000),
    ("agreed to pay $40 million to settle", 40_000_000),
]
all_ok = True
for text, expected in tests:
    got = _extract_penalty_from_text(text)
    status = 'OK' if got == expected else f'FAIL (got {got})'
    if got != expected:
        all_ok = False
    print(f'{status}: {text[:55]}')
print("ALL OK" if all_ok else "SOME TESTS FAILED")
