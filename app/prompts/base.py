CLASSIFY_PROMPT = """You are classifying a medical document.

Decide which of the following categories the image represents:
- referral_letter: a doctor's referral letter to a specialist or lab
- medical_certificate: a sick note / MC granting medical leave
- receipt: a payment receipt or invoice for medical services
- unknown: none of the above

Respond with the single category string only."""


COMMON_EXTRACTION_RULES = """\
Rules:
- Dates must be returned in DD/MM/YYYY format (e.g. "12/03/1985").
- Amounts must be returned as digit strings with all currency symbols,
  thousands separators, and decimals removed. Example: "$30,000.00" -> "3000000".
- If a field is missing, illegible, or you are not confident, return null.
- provider_name must NOT contain the literal string "Fullerton Health".
  If the provider is Fullerton Health, return null for provider_name.
- signature_presence is true ONLY for handwritten cursive signatures.
  Printed names, typed signatures, or stamps are false.
- Do not invent values. Only extract what is visible in the document."""


def build_extraction_prompt(doc_type_label: str, field_descriptions: str) -> str:
    return f"""You are extracting structured data from a {doc_type_label}.

Extract these fields exactly as named:
{field_descriptions}

{COMMON_EXTRACTION_RULES}

Return JSON matching the provided schema."""


REPAIR_WRAPPER_TEMPLATE = """\

A previous extraction attempt on this same document had issues:

{failure_summary}
{raw_text_hint}
Re-extract the document carefully. Pay particular attention to the fields
listed above. Follow all original extraction rules."""


def build_repair_prompt(
    base_prompt: str,
    failure_summary: str,
    raw_text_hint: str = "",
) -> str:
    hint_block = ""
    if raw_text_hint.strip():
        hint_block = (
            "\nRelevant excerpts from the document's raw text:\n"
            "---\n"
            f"{raw_text_hint.strip()}\n"
            "---\n"
        )
    wrapper = REPAIR_WRAPPER_TEMPLATE.format(
        failure_summary=failure_summary,
        raw_text_hint=hint_block,
    )
    return base_prompt + "\n" + wrapper
