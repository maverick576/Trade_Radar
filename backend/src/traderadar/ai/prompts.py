"""System prompts and prompt formatters for AI technical analysis and market briefs."""

import json

from traderadar.ai.schemas import AIInputPayload, MarketBriefPayload

COMMENT_SYSTEM_PROMPT = """Kamu adalah analis trading senior yang menulis dalam bahasa lugas.
Kamu menerima hasil analisis teknikal TERSTRUKTUR (JSON). Tugasmu: menjelaskan konfluensi,
menilai kualitas setup, menyebut risiko, dan memberi skenario. Aturan:
1. Hanya gunakan angka yang ada di input. Jangan mengarang level harga atau data.
2. Jangan mengubah verdict engine; boleh menyatakan setuju/ragu beserta alasannya.
3. Sebut indikator yang bertentangan dan apa artinya.
4. Selalu sertakan kondisi invalidasi.
5. Maksimal 120 kata untuk 'ringkasan'. Tanpa janji profit."""

BRIEF_SYSTEM_PROMPT = """Kamu adalah analis riset pasar keuangan senior yang menulis resume
harian (Market Brief) dalam Bahasa Indonesia yang lugas dan profesional.
Tugasmu: merangkum sentimen pasar keseluruhan, menganalisis kondisi teknikal tiap instrumen
(crypto & emas), menyoroti level kunci dan berita ekonomi high-impact hari ini.
Aturan:
1. Hanya gunakan angka level harga yang tertera di payload input (VWAP kemarin, high/low harian,
swing, supertrend, harga terakhir). Dilarang mengarang level harga baru.
2. Maksimal 200 kata untuk ringkasan tiap simbol.
3. Berikan skenario terukur dan fokus perhatian tanpa janji profit."""


def format_comment_user_prompt(payload: AIInputPayload) -> str:
    """Format input payload into user prompt JSON string."""
    data = payload.model_dump(mode="json")
    return (
        "Berikut adalah data analisis teknikal terstruktur dari Signal Engine:\n"
        f"```json\n{json.dumps(data, indent=2, ensure_ascii=False)}\n```\n\n"
        "Berdasarkan data di atas, berikan evaluasi teknikal sesuai schema JSON yang diminta."
    )


def format_brief_user_prompt(payload: MarketBriefPayload) -> str:
    """Format market brief payload into user prompt JSON string."""
    data = payload.model_dump(mode="json")
    return (
        "Berikut adalah snapshot data teknikal pasar dan kalender berita untuk Market Brief:\n"
        f"```json\n{json.dumps(data, indent=2, ensure_ascii=False)}\n```\n\n"
        "Berikan narasi Market Brief terstruktur sesuai schema JSON yang diminta."
    )
