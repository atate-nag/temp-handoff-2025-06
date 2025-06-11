import re

def normalise_cites(text: str) -> str:
    # 2021-mckinsey-global-payments-report.pdf → (Mckinsey, 2021)
    text = re.sub(
        r"([A-Za-z0-9._-]+?)(?:\.pdf)?,?(\d{4})",
        lambda m: f"({m[1].split('_')[0].title()}, {m[2]})",
        text,
    )
    return text
