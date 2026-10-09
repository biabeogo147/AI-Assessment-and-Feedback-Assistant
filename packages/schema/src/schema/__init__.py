"""Schema Postgres, dùng chung bởi hai service cùng ghi vào nó.

Package này **không re-export gì cả**, khác `contracts`. Lý do: `contracts` là một bảng từ
vựng phẳng — một người gọi cần `DocumentProbed` thì không quan tâm nó ở file nào. Còn ở đây
có đúng hai mặt, và chúng không thay nhau được:

- `schema.models` — khai báo bảng. Thứ mọi truy vấn cần.
- `schema.ddl` — câu lệnh **về** schema: dựng, đối chiếu, dựng lại. Thứ đúng hai chỗ trong cả
  repo được gọi tới.

Một `__init__` kéo cả hai lên cùng một tên sẽ làm `from schema import prepare_schema` đọc ra
vô hại đúng bằng `from schema import Document`, trong khi một cái là một lệnh DDL trên database
thật và cái kia là một khai báo. Đường rạch ấy là nửa giá trị của package này, nên nó được giữ
ở ngay chỗ người ta gõ.
"""
