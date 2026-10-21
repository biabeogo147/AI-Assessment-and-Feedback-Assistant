"""Dữ liệu lab: 5 giáo viên, 30 lớp, 1000 học sinh, đề ở mọi trạng thái (plan `lab-deploy-aws`).

Khác `be.seed`: demo kể **một** câu chuyện cho khớp Figma; lab kể đủ chuyện để năm người thử tay
mà thấy được các màn ở lúc đầy dữ liệu. Chạy bằng `python -m be.lab_seed --reset`.
"""

from be.lab_seed.story import LabSummary, seed_lab

__all__ = ["LabSummary", "seed_lab"]
