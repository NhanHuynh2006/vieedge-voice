"""Prompts for spoken Vietnamese Q&A. The system prompt is fixed so its KV cache is computed once
at start-up and reused for every question (M4)."""
from __future__ import annotations

SYSTEM_PROMPT = (
    "Bạn là VieEdge, trợ lý hỏi đáp bằng giọng nói tiếng Việt chạy hoàn toàn trên thiết bị, không có internet. "
    "Câu trả lời của bạn sẽ được đọc to bằng giọng nói, vì vậy hãy: "
    "trả lời ngắn gọn trong 1 đến 3 câu; dùng câu văn nói tự nhiên, thân thiện; "
    "không dùng markdown, không gạch đầu dòng, không ký hiệu, không biểu tượng cảm xúc; "
    "viết số và đơn vị sao cho dễ đọc. "
    "Nếu câu hỏi cần thông tin thời gian thực (thời tiết, tin tức, giá cả hôm nay, tỷ số) hoặc bạn không chắc chắn, "
    "hãy nói thật là mình không chắc hoặc không có thông tin đó, tuyệt đối không bịa."
)


RAG_TEMPLATE = (
    "Thông tin tham khảo: {context}\n"
    "Câu hỏi: {question}\n"
    "Nếu thông tin không liên quan, hãy nói bạn không chắc."
)


def build_messages(question: str, history: list[tuple[str, str]] | None = None,
                   system: str = SYSTEM_PROMPT, context: str | None = None) -> list[dict]:
    msgs = [{"role": "system", "content": system}]
    for q, a in history or []:
        msgs += [{"role": "user", "content": q}, {"role": "assistant", "content": a}]
    user = RAG_TEMPLATE.format(context=context, question=question.strip()) if context else question.strip()
    msgs.append({"role": "user", "content": user})
    return msgs
