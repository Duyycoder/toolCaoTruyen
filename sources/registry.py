from typing import Dict, Type
from sources.base import BaseSourceParser
from sources.shuba69 import Shuba69Parser

# Đăng ký các Strategy Parser
SOURCES: Dict[str, Type[BaseSourceParser]] = {
    "69shuba": Shuba69Parser
}

def get_source(name: str, base_url: str) -> BaseSourceParser:
    """Khởi tạo và trả về instance của parser tương ứng với tên nguồn.

    Args:
        name: Tên nguồn truyện (ví dụ: "69shuba").
        base_url: Base URL để truyền vào parser.

    Returns:
        Instance của BaseSourceParser.
    """
    if name not in SOURCES:
        raise ValueError(
            f"Không hỗ trợ nguồn truyện: {name}. "
            f"Các nguồn hỗ trợ: {list(SOURCES.keys())}"
        )
    return SOURCES[name](base_url=base_url)
