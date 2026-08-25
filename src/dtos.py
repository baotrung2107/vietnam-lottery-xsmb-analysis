__author__ = 'Khiem Doan'
__github__ = 'https://github.com/khiemdoan'
__email__ = 'doankhiem.crazy@gmail.com'

from datetime import date
from typing import Annotated

from pydantic import BaseModel, Field, RootModel

# Miền giá trị hợp lệ của từng hạng giải, suy ra từ độ rộng hiển thị trong templates/README.j2:
# giải đặc biệt/nhất/nhì/ba 5 chữ số, giải tư/năm 4 chữ số, giải sáu 3 chữ số, giải bảy 2 chữ số.
Prize5Digits = Annotated[int, Field(ge=0, le=99999)]
Prize4Digits = Annotated[int, Field(ge=0, le=9999)]
Prize3Digits = Annotated[int, Field(ge=0, le=999)]
Prize2Digits = Annotated[int, Field(ge=0, le=99)]


class Result(BaseModel):
    date: date

    special: Prize5Digits

    prize1: Prize5Digits

    prize2_1: Prize5Digits
    prize2_2: Prize5Digits

    prize3_1: Prize5Digits
    prize3_2: Prize5Digits
    prize3_3: Prize5Digits
    prize3_4: Prize5Digits
    prize3_5: Prize5Digits
    prize3_6: Prize5Digits

    prize4_1: Prize4Digits
    prize4_2: Prize4Digits
    prize4_3: Prize4Digits
    prize4_4: Prize4Digits

    prize5_1: Prize4Digits
    prize5_2: Prize4Digits
    prize5_3: Prize4Digits
    prize5_4: Prize4Digits
    prize5_5: Prize4Digits
    prize5_6: Prize4Digits

    prize6_1: Prize3Digits
    prize6_2: Prize3Digits
    prize6_3: Prize3Digits

    prize7_1: Prize2Digits
    prize7_2: Prize2Digits
    prize7_3: Prize2Digits
    prize7_4: Prize2Digits

    def prizes(self) -> tuple[int, ...]:
        """27 con số của kỳ quay, bỏ cột ngày — dùng làm khoá phát hiện hai ngày trùng kết quả."""
        return tuple(value for name, value in self.model_dump().items() if name != 'date')


class ResultList(RootModel):
    root: list[Result]
