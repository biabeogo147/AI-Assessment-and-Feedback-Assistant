"""Câu song sinh thứ hai và thứ ba cho mỗi câu của seed lab: một vòng chữa một đề mới (ADR-17).

Đường thật từ chối một câu vòng chữa lặp lại câu gốc hay một vòng trước (`validate_retry`), vì
vòng chữa kiểm xem em đã sửa được lỗi chưa, không kiểm trí nhớ. Một câu đi đủ ba vòng nên cần ba
đề khác nhau: `Item.twin` là đề vòng 1, hai đề ở đây là vòng 2 và 3. Khoá là đề bài câu gốc.

`services/be/tests/test_lab_seed.py` chạy chính `validate_question` và `validate_retry` của BE
trên mọi đề ở đây.
"""

from be.lab_seed.papers import Item, Twin

_MORE: dict[str, tuple[Twin, Twin]] = {
    # ------------------------------------------------------------------ Hàm số bậc hai
    "Đỉnh của parabol y = x² − 4x + 3 là điểm nào?": (
        Twin(
            "Đỉnh của parabol y = x² − 6x + 5 là điểm nào?",
            (
                ("A", "(3; −4)", True, None),
                ("B", "(−3; 32)", False, "đổi dấu hoành độ đỉnh"),
                ("C", "(3; 5)", False, "lấy hệ số tự do làm tung độ đỉnh"),
                ("D", "(6; 5)", False, "dùng −b/a thay cho −b/(2a)"),
            ),
            (
                ("Công thức đỉnh", "x = −b/(2a) = 3, thay lại: y(3) = 9 − 18 + 5 = −4."),
                ("Đưa về dạng bình phương", "y = (x − 3)² − 4, đỉnh (3; −4)."),
            ),
        ),
        Twin(
            "Đỉnh của parabol y = x² + 4x + 1 là điểm nào?",
            (
                ("A", "(−2; −3)", True, None),
                ("B", "(2; 13)", False, "đổi dấu hoành độ đỉnh"),
                ("C", "(−2; 1)", False, "lấy hệ số tự do làm tung độ đỉnh"),
                ("D", "(−4; 1)", False, "dùng −b/a thay cho −b/(2a)"),
            ),
            (
                ("Công thức đỉnh", "x = −4/2 = −2, thay lại: y(−2) = 4 − 8 + 1 = −3."),
                ("Đưa về dạng bình phương", "y = (x + 2)² − 3, đỉnh (−2; −3)."),
            ),
        ),
    ),
    "Trục đối xứng của parabol y = 2x² − 8x + 1 là đường nào?": (
        Twin(
            "Trục đối xứng của parabol y = 3x² + 12x − 4 là đường nào?",
            (
                ("A", "x = −2", True, None),
                ("B", "x = 2", False, "sai dấu trong công thức −b/(2a)"),
                ("C", "x = −4", False, "dùng −b/a thay cho −b/(2a)"),
                ("D", "y = −2", False, "nhầm trục đối xứng với một đường nằm ngang"),
            ),
            (
                ("Công thức", "x = −b/(2a) = −12/6 = −2."),
                ("Hai điểm đối xứng", "y(0) = y(−4) = −4, trung điểm của 0 và −4 là −2."),
            ),
        ),
        Twin(
            "Trục đối xứng của parabol y = x² − 10x + 7 là đường nào?",
            (
                ("A", "x = 5", True, None),
                ("B", "x = −5", False, "sai dấu trong công thức −b/(2a)"),
                ("C", "x = 10", False, "dùng −b/a thay cho −b/(2a)"),
                ("D", "y = 5", False, "nhầm trục đối xứng với một đường nằm ngang"),
            ),
            (
                ("Công thức", "x = −b/(2a) = 10/2 = 5."),
                ("Hai điểm đối xứng", "y(0) = y(10) = 7, trung điểm của 0 và 10 là 5."),
            ),
        ),
    ),
    "Hàm số y = −x² + 2x + 3 đồng biến trên khoảng nào?": (
        Twin(
            "Hàm số y = −x² + 4x − 3 đồng biến trên khoảng nào?",
            (
                ("A", "(−∞; 2)", True, None),
                ("B", "(2; +∞)", False, "quên rằng a < 0 làm đảo chiều biến thiên"),
                ("C", "(1; 3)", False, "lấy khoảng giữa hai nghiệm"),
                ("D", "(−∞; 3)", False, "lấy nghiệm làm mốc thay cho hoành độ đỉnh"),
            ),
            (
                ("Theo dấu của a", "a < 0: tăng bên trái đỉnh x = 2, giảm bên phải."),
                ("Bảng biến thiên", "Lập bảng quanh x = 2 rồi đọc chiều trên từng khoảng."),
            ),
        ),
        Twin(
            "Hàm số y = x² − 2x − 8 đồng biến trên khoảng nào?",
            (
                ("A", "(1; +∞)", True, None),
                ("B", "(−∞; 1)", False, "quên rằng chiều biến thiên đi theo dấu của a"),
                ("C", "(−2; 4)", False, "lấy khoảng giữa hai nghiệm"),
                ("D", "(4; +∞)", False, "lấy nghiệm làm mốc thay cho hoành độ đỉnh"),
            ),
            (
                ("Theo dấu của a", "a > 0: giảm bên trái đỉnh x = 1, tăng bên phải."),
                ("Bảng biến thiên", "Lập bảng quanh x = 1 rồi đọc chiều trên từng khoảng."),
            ),
        ),
    ),
    "Giá trị nhỏ nhất của hàm số y = x² − 2x + 5 bằng bao nhiêu?": (
        Twin(
            "Giá trị nhỏ nhất của hàm số y = x² − 6x + 10 bằng bao nhiêu?",
            (
                ("A", "1", True, None),
                ("B", "3", False, "lấy hoành độ đỉnh thay cho giá trị nhỏ nhất"),
                ("C", "10", False, "lấy hệ số tự do"),
                ("D", "0", False, "nghĩ parabol nào cũng chạm trục hoành"),
            ),
            (
                ("Tung độ đỉnh", "a > 0 nên giá trị nhỏ nhất là y(3) = 9 − 18 + 10 = 1."),
                ("Hằng đẳng thức", "y = (x − 3)² + 1 ≥ 1, dấu bằng khi x = 3."),
            ),
        ),
        Twin(
            "Giá trị nhỏ nhất của hàm số y = 2x² + 8x + 11 bằng bao nhiêu?",
            (
                ("A", "3", True, None),
                ("B", "−2", False, "lấy hoành độ đỉnh thay cho giá trị nhỏ nhất"),
                ("C", "11", False, "lấy hệ số tự do"),
                ("D", "0", False, "nghĩ parabol nào cũng chạm trục hoành"),
            ),
            (
                ("Tung độ đỉnh", "Đỉnh x = −8/4 = −2, y(−2) = 8 − 16 + 11 = 3."),
                ("Hằng đẳng thức", "y = 2(x + 2)² + 3 ≥ 3, dấu bằng khi x = −2."),
            ),
        ),
    ),
    "Parabol y = x² − 5x + 6 cắt trục hoành tại những điểm có hoành độ nào?": (
        Twin(
            "Parabol y = x² − 7x + 12 cắt trục hoành tại những điểm có hoành độ nào?",
            (
                ("A", "x = 3 và x = 4", True, None),
                ("B", "x = −3 và x = −4", False, "đổi dấu nghiệm"),
                ("C", "x = 2 và x = 6", False, "phân tích sai thành nhân tử"),
                ("D", "Không cắt", False, "tính sai biệt thức"),
            ),
            (
                ("Giải phương trình", "x² − 7x + 12 = 0, Δ = 1 > 0, hai nghiệm 3 và 4."),
                ("Định lí Vi-ét", "Tìm hai số có tổng 7 và tích 12."),
            ),
        ),
        Twin(
            "Parabol y = x² + x − 12 cắt trục hoành tại những điểm có hoành độ nào?",
            (
                ("A", "x = −4 và x = 3", True, None),
                ("B", "x = 4 và x = −3", False, "đổi dấu nghiệm"),
                ("C", "x = 2 và x = −6", False, "phân tích sai thành nhân tử"),
                ("D", "Không cắt", False, "tính sai biệt thức"),
            ),
            (
                ("Giải phương trình", "x² + x − 12 = 0, Δ = 49, hai nghiệm −4 và 3."),
                ("Định lí Vi-ét", "Tìm hai số có tổng −1 và tích −12."),
            ),
        ),
    ),
    "Parabol y = ax² + bx + c có đỉnh (2; 0) và đi qua (0; 12). Hệ số a bằng bao nhiêu?": (
        Twin(
            "Parabol y = ax² + bx + c có đỉnh (−2; 0), đi qua (0; 8). Tìm hệ số a.",
            (
                ("A", "2", True, None),
                ("B", "−2", False, "sai dấu khi thay toạ độ điểm"),
                ("C", "4", False, "quên bình phương khoảng cách tới đỉnh"),
                ("D", "8", False, "lấy tung độ giao điểm với trục tung làm a"),
            ),
            (
                ("Dạng đỉnh", "y = a(x + 2)²; thay (0; 8) được 4a = 8, nên a = 2."),
                ("Hệ phương trình", "Lập hệ từ c = 8, −b/(2a) = −2 và y(−2) = 0 rồi giải."),
            ),
        ),
        Twin(
            "Parabol y = ax² + bx + c có đỉnh (2; 0), đi qua (0; −8). Tìm hệ số a.",
            (
                ("A", "−2", True, None),
                ("B", "2", False, "sai dấu khi thay toạ độ điểm"),
                ("C", "−4", False, "quên bình phương khoảng cách tới đỉnh"),
                ("D", "−8", False, "lấy tung độ giao điểm với trục tung làm a"),
            ),
            (
                ("Dạng đỉnh", "y = a(x − 2)²; thay (0; −8) được 4a = −8, nên a = −2."),
                ("Hệ phương trình", "Lập hệ từ c = −8, −b/(2a) = 2 và y(2) = 0 rồi giải."),
            ),
        ),
    ),
    # ------------------------------------------------------------------ Mệnh đề và tập hợp
    "Mệnh đề phủ định của “∀x ∈ ℝ, x² ≥ 0” là mệnh đề nào?": (
        Twin(
            "Mệnh đề phủ định của “∀x ∈ ℝ, x + 1 > x” là mệnh đề nào?",
            (
                ("A", "∃x ∈ ℝ, x + 1 ≤ x", True, None),
                ("B", "∀x ∈ ℝ, x + 1 ≤ x", False, "giữ nguyên lượng từ ∀"),
                ("C", "∃x ∈ ℝ, x + 1 > x", False, "đổi lượng từ nhưng quên phủ định vế sau"),
                ("D", "∀x ∈ ℝ, x + 1 < x", False, "phủ định > thành <"),
            ),
            (
                ("Hai bước", "Đổi ∀ thành ∃, rồi phủ định tính chất: > thành ≤."),
                ("Kiểm bằng nghĩa", "Mệnh đề gốc sai khi có ít nhất một x làm x + 1 ≤ x."),
            ),
        ),
        Twin(
            "Mệnh đề phủ định của “∃n ∈ ℕ, n² = 2n” là mệnh đề nào?",
            (
                ("A", "∀n ∈ ℕ, n² ≠ 2n", True, None),
                ("B", "∃n ∈ ℕ, n² ≠ 2n", False, "giữ nguyên lượng từ ∃"),
                ("C", "∀n ∈ ℕ, n² = 2n", False, "đổi lượng từ nhưng quên phủ định vế sau"),
                ("D", "∃n ∈ ℕ, n² > 2n", False, "phủ định = thành >"),
            ),
            (
                ("Hai bước", "Đổi ∃ thành ∀, rồi phủ định tính chất: = thành ≠."),
                ("Kiểm bằng nghĩa", "Mệnh đề gốc sai khi không có số tự nhiên nào làm n² = 2n."),
            ),
        ),
    ),
    "Cho A = {1; 2; 3; 4} và B = {3; 4; 5}. Tập A ∩ B là tập nào?": (
        Twin(
            "Cho A = {a; b; c; d} và B = {b; d; e}. Tập A ∩ B là tập nào?",
            (
                ("A", "{b; d}", True, None),
                ("B", "{a; b; c; d; e}", False, "nhầm giao với hợp"),
                ("C", "{a; c}", False, "lấy A \\ B"),
                ("D", "{e}", False, "lấy B \\ A"),
            ),
            (
                ("Theo định nghĩa", "A ∩ B gồm các phần tử thuộc cả A lẫn B: b và d."),
                ("Biểu đồ Ven", "Vẽ hai vòng tròn, phần chung là giao."),
            ),
        ),
        Twin(
            "Cho A = {0; 1; 2; 3} và B = {1; 3; 5; 7}. Tập A ∩ B là tập nào?",
            (
                ("A", "{1; 3}", True, None),
                ("B", "{0; 1; 2; 3; 5; 7}", False, "nhầm giao với hợp"),
                ("C", "{0; 2}", False, "lấy A \\ B"),
                ("D", "{5; 7}", False, "lấy B \\ A"),
            ),
            (
                ("Theo định nghĩa", "A ∩ B gồm các phần tử thuộc cả A lẫn B: 1 và 3."),
                ("Biểu đồ Ven", "Vẽ hai vòng tròn, phần chung là giao."),
            ),
        ),
    ),
    "Cho A = [1; 5) và B = (3; 7]. Tập A ∪ B là tập nào?": (
        Twin(
            "Cho A = [0; 4) và B = (2; 6]. Tập A ∪ B là tập nào?",
            (
                ("A", "[0; 6]", True, None),
                ("B", "(2; 4)", False, "nhầm hợp với giao"),
                ("C", "[0; 2]", False, "lấy A \\ B"),
                ("D", "[0; 6)", False, "đọc sai đầu mút của B"),
            ),
            (
                ("Trục số", "Tô cả hai khoảng trên trục số, hợp là toàn bộ phần đã tô."),
                ("Đầu mút", "Đầu mút trái 0 lấy của A (đóng), đầu mút phải 6 lấy của B (đóng)."),
            ),
        ),
        Twin(
            "Cho A = (−3; 2] và B = [0; 5). Tập A ∪ B là tập nào?",
            (
                ("A", "(−3; 5)", True, None),
                ("B", "[0; 2]", False, "nhầm hợp với giao"),
                ("C", "(−3; 0)", False, "lấy A \\ B"),
                ("D", "(−3; 5]", False, "đọc sai đầu mút của B"),
            ),
            (
                ("Trục số", "Tô cả hai khoảng trên trục số, hợp là toàn bộ phần đã tô."),
                ("Đầu mút", "Đầu mút trái −3 lấy của A (mở), đầu mút phải 5 lấy của B (mở)."),
            ),
        ),
    ),
    "Tập {a; b; c} có bao nhiêu tập con?": (
        Twin(
            "Tập {1; 2; 3; 4; 5} có bao nhiêu tập con?",
            (
                ("A", "32", True, None),
                ("B", "30", False, "quên tập rỗng và chính tập đó"),
                ("C", "31", False, "quên tập rỗng"),
                ("D", "5", False, "chỉ đếm tập con một phần tử"),
            ),
            (
                ("Công thức", "Tập có n phần tử có 2ⁿ tập con; ở đây 2⁵ = 32."),
                ("Liệt kê theo cỡ", "1 + 5 + 10 + 10 + 5 + 1 = 32."),
            ),
        ),
        Twin(
            "Tập {a; b; c; d; e; f} có bao nhiêu tập con?",
            (
                ("A", "64", True, None),
                ("B", "62", False, "quên tập rỗng và chính tập đó"),
                ("C", "63", False, "quên tập rỗng"),
                ("D", "6", False, "chỉ đếm tập con một phần tử"),
            ),
            (
                ("Công thức", "Tập có n phần tử có 2ⁿ tập con; ở đây 2⁶ = 64."),
                ("Mỗi phần tử hai cách", "Mỗi phần tử có hoặc không có mặt: 2 · 2 · … · 2 = 64."),
            ),
        ),
    ),
    "Mệnh đề nào sau đây đúng?": (
        Twin(
            "Chọn mệnh đề đúng trong các mệnh đề sau.",
            (
                ("A", "√16 là số hữu tỉ", True, None),
                ("B", "√25 là số vô tỉ", False, "không rút gọn căn trước khi xét"),
                ("C", "−10 > −4", False, "so sánh số âm theo trị tuyệt đối"),
                ("D", "1/6 = 0,17", False, "nhầm giá trị gần đúng với giá trị đúng"),
            ),
            (
                ("Xét từng mệnh đề", "√16 = 4 là số nguyên, nên là số hữu tỉ."),
                ("Phản ví dụ", "Ba mệnh đề còn lại mỗi cái sai ở một chỗ: kiểm từng chỗ."),
            ),
        ),
        Twin(
            "Trong bốn khẳng định dưới đây, khẳng định nào đúng?",
            (
                ("A", "π là số vô tỉ", True, None),
                ("B", "√49 là số vô tỉ", False, "không rút gọn căn trước khi xét"),
                ("C", "−8 > −1", False, "so sánh số âm theo trị tuyệt đối"),
                ("D", "5/7 = 0,71", False, "nhầm giá trị gần đúng với giá trị đúng"),
            ),
            (
                ("Xét từng mệnh đề", "π không viết được thành phân số, nên là số vô tỉ."),
                ("Phản ví dụ", "√49 = 7; −8 < −1; 5/7 = 0,714…"),
            ),
        ),
    ),
    "Cho A = {x ∈ ℝ | x² − 3x + 2 = 0}. Liệt kê các phần tử của A.": (
        Twin(
            "Cho A = {x ∈ ℝ | x² − 7x + 10 = 0}. Liệt kê các phần tử của A.",
            (
                ("A", "{2; 5}", True, None),
                ("B", "{−2; −5}", False, "đổi dấu nghiệm"),
                ("C", "{7; 10}", False, "lấy hệ số làm phần tử"),
                ("D", "∅", False, "tính sai biệt thức"),
            ),
            (
                ("Giải phương trình", "x² − 7x + 10 = (x − 2)(x − 5) = 0."),
                ("Thử lại", "Thay 2 và 5 vào phương trình."),
            ),
        ),
        Twin(
            "Cho A = {x ∈ ℝ | x² − 6x + 8 = 0}. Liệt kê các phần tử của A.",
            (
                ("A", "{2; 4}", True, None),
                ("B", "{−2; −4}", False, "đổi dấu nghiệm"),
                ("C", "{6; 8}", False, "lấy hệ số làm phần tử"),
                ("D", "∅", False, "tính sai biệt thức"),
            ),
            (
                ("Giải phương trình", "x² − 6x + 8 = (x − 2)(x − 4) = 0."),
                ("Thử lại", "Thay 2 và 4 vào phương trình."),
            ),
        ),
    ),
    # ------------------------------------------------------------------ Lượng giác
    "Đổi 60° ra radian.": (
        Twin(
            "Đổi 45° ra radian.",
            (
                ("A", "π/4", True, None),
                ("B", "π/2", False, "nhầm 45° với 90°"),
                ("C", "4/π", False, "lật ngược tỉ số π/180"),
                ("D", "45π", False, "quên chia cho 180"),
            ),
            (
                ("Tỉ số", "45 · π/180 = π/4."),
                ("Góc quen", "45° là một phần tư của 180°, nên là π/4."),
            ),
        ),
        Twin(
            "Đổi 150° ra radian.",
            (
                ("A", "5π/6", True, None),
                ("B", "π/6", False, "chỉ đổi phần 30°"),
                ("C", "6/(5π)", False, "lật ngược tỉ số π/180"),
                ("D", "150π", False, "quên chia cho 180"),
            ),
            (
                ("Tỉ số", "150 · π/180 = 5π/6."),
                ("Góc quen", "150° = 180° − 30°, nên là π − π/6 = 5π/6."),
            ),
        ),
    ),
    "sin(π/6) bằng bao nhiêu?": (
        Twin(
            "cos(π/6) bằng bao nhiêu?",
            (
                ("A", "√3/2", True, None),
                ("B", "1/2", False, "nhầm cos với sin"),
                ("C", "√2/2", False, "lấy giá trị của góc π/4"),
                ("D", "1", False, "nhầm với cos 0"),
            ),
            (
                ("Đường tròn lượng giác", "Điểm ứng với π/6 có hoành độ √3/2."),
                ("Tam giác nửa đều", "Cạnh kề góc 30° bằng √3/2 cạnh huyền."),
            ),
        ),
        Twin(
            "sin(π/3) bằng bao nhiêu?",
            (
                ("A", "√3/2", True, None),
                ("B", "1/2", False, "nhầm sin với cos"),
                ("C", "√2/2", False, "lấy giá trị của góc π/4"),
                ("D", "1", False, "nhầm với sin(π/2)"),
            ),
            (
                ("Đường tròn lượng giác", "Điểm ứng với π/3 có tung độ √3/2."),
                ("Tam giác nửa đều", "Cạnh đối diện góc 60° bằng √3/2 cạnh huyền."),
            ),
        ),
    ),
    "Phương trình sin x = 0 có nghiệm là gì?": (
        Twin(
            "Phương trình sin x = 1 có nghiệm là gì?",
            (
                ("A", "x = π/2 + k2π, k ∈ ℤ", True, None),
                ("B", "x = π/2 + kπ, k ∈ ℤ", False, "lấy cả nghiệm của sin x = −1"),
                ("C", "x = k2π, k ∈ ℤ", False, "nhầm với cos x = 1"),
                ("D", "x = kπ, k ∈ ℤ", False, "nhầm với sin x = 0"),
            ),
            (
                ("Đường tròn lượng giác", "Tung độ bằng 1 chỉ tại điểm π/2, lặp lại sau mỗi 2π."),
                ("Đồ thị", "y = sin x đạt giá trị lớn nhất 1 tại π/2 + k2π."),
            ),
        ),
        Twin(
            "Phương trình cos x = 1 có nghiệm là gì?",
            (
                ("A", "x = k2π, k ∈ ℤ", True, None),
                ("B", "x = kπ, k ∈ ℤ", False, "lấy cả nghiệm của cos x = −1"),
                ("C", "x = π/2 + k2π, k ∈ ℤ", False, "nhầm với sin x = 1"),
                ("D", "x = π/2 + kπ, k ∈ ℤ", False, "nhầm với cos x = 0"),
            ),
            (
                ("Đường tròn lượng giác", "Hoành độ bằng 1 chỉ tại điểm 0, lặp lại sau mỗi 2π."),
                ("Đồ thị", "y = cos x đạt giá trị lớn nhất 1 tại k2π."),
            ),
        ),
    ),
    "Chu kì tuần hoàn của hàm số y = sin 2x là bao nhiêu?": (
        Twin(
            "Chu kì tuần hoàn của hàm số y = sin 4x là bao nhiêu?",
            (
                ("A", "π/2", True, None),
                ("B", "2π", False, "quên chia cho hệ số của x"),
                ("C", "8π", False, "nhân với hệ số thay vì chia"),
                ("D", "π/8", False, "chia cho hệ số hai lần"),
            ),
            (
                ("Công thức", "y = sin(ax) có chu kì 2π/|a|; ở đây 2π/4 = π/2."),
                ("Kiểm lại", "sin 4(x + π/2) = sin(4x + 2π) = sin 4x."),
            ),
        ),
        Twin(
            "Chu kì tuần hoàn của hàm số y = cos(x/2) là bao nhiêu?",
            (
                ("A", "4π", True, None),
                ("B", "2π", False, "quên chia cho hệ số của x"),
                ("C", "π", False, "nhân với hệ số thay vì chia"),
                ("D", "8π", False, "chia cho hệ số hai lần"),
            ),
            (
                ("Công thức", "y = cos(ax) có chu kì 2π/|a|; ở đây 2π : (1/2) = 4π."),
                ("Kiểm lại", "cos((x + 4π)/2) = cos(x/2 + 2π) = cos(x/2)."),
            ),
        ),
    ),
    "Cho cos α = 3/5 với α là góc nhọn. Tính sin α.": (
        Twin(
            "Cho cos α = 8/17 với α là góc nhọn. Tính sin α.",
            (
                ("A", "15/17", True, None),
                ("B", "−15/17", False, "quên rằng góc nhọn có sin dương"),
                ("C", "9/17", False, "lấy 1 − cos α"),
                ("D", "225/289", False, "quên lấy căn bậc hai"),
            ),
            (
                ("Hệ thức", "sin²α = 1 − 64/289 = 225/289, α nhọn nên sin α = 15/17."),
                ("Tam giác vuông", "Cạnh kề 8, cạnh huyền 17 thì cạnh đối là 15."),
            ),
        ),
        Twin(
            "Cho sin α = 3/5 với α là góc nhọn. Tính cos α.",
            (
                ("A", "4/5", True, None),
                ("B", "−4/5", False, "quên rằng góc nhọn có cos dương"),
                ("C", "2/5", False, "lấy 1 − sin α"),
                ("D", "16/25", False, "quên lấy căn bậc hai"),
            ),
            (
                ("Hệ thức", "cos²α = 1 − 9/25 = 16/25, α nhọn nên cos α = 4/5."),
                ("Tam giác vuông", "Cạnh đối 3, cạnh huyền 5 thì cạnh kề là 4."),
            ),
        ),
    ),
    "Nghiệm của phương trình 2cos x − 1 = 0 trên đoạn [0; π] là gì?": (
        Twin(
            "Nghiệm của phương trình 2sin x − 1 = 0 trên đoạn [0; π/2] là gì?",
            (
                ("A", "x = π/6", True, None),
                ("B", "x = π/3", False, "nhầm giá trị của sin với cos"),
                ("C", "x = 5π/6", False, "lấy nghiệm nằm ngoài đoạn"),
                ("D", "x = π/4", False, "lấy giá trị của góc π/4"),
            ),
            (
                ("Đưa về cơ bản", "sin x = 1/2, trên [0; π/2] chỉ có x = π/6."),
                ("Đường tròn", "Tung độ 1/2 ứng với π/6 và 5π/6; chỉ π/6 nằm trong đoạn."),
            ),
        ),
        Twin(
            "Nghiệm của phương trình 2cos x − √2 = 0 trên đoạn [0; π/2] là gì?",
            (
                ("A", "x = π/4", True, None),
                ("B", "x = π/3", False, "nhầm √2/2 với 1/2"),
                ("C", "x = −π/4", False, "lấy nghiệm nằm ngoài đoạn"),
                ("D", "x = π/6", False, "lấy giá trị của góc π/6"),
            ),
            (
                ("Đưa về cơ bản", "cos x = √2/2, trên [0; π/2] chỉ có x = π/4."),
                ("Đường tròn", "Hoành độ √2/2 ứng với ±π/4; chỉ π/4 nằm trong đoạn."),
            ),
        ),
    ),
    # ------------------------------------------------------------------ Cấp số cộng, cấp số nhân
    "Cấp số cộng có u₁ = 2 và công sai d = 3. Tính u₅.": (
        Twin(
            "Cấp số cộng có u₁ = 4 và công sai d = 5. Tính u₇.",
            (
                ("A", "34", True, None),
                ("B", "39", False, "dùng n·d thay cho (n − 1)·d"),
                ("C", "29", False, "dùng (n − 2)·d"),
                ("D", "140", False, "nhân thay vì cộng"),
            ),
            (
                ("Công thức", "uₙ = u₁ + (n − 1)d = 4 + 6 · 5 = 34."),
                ("Cộng dần", "4, 9, 14, 19, 24, 29, 34."),
            ),
        ),
        Twin(
            "Cấp số cộng có u₁ = −3 và công sai d = 4. Tính u₅.",
            (
                ("A", "13", True, None),
                ("B", "17", False, "dùng n·d thay cho (n − 1)·d"),
                ("C", "9", False, "dùng (n − 2)·d"),
                ("D", "−60", False, "nhân thay vì cộng"),
            ),
            (
                ("Công thức", "uₙ = u₁ + (n − 1)d = −3 + 4 · 4 = 13."),
                ("Cộng dần", "−3, 1, 5, 9, 13."),
            ),
        ),
    ),
    "Cấp số nhân có u₁ = 3 và công bội q = 2. Tính u₄.": (
        Twin(
            "Cấp số nhân có u₁ = 5 và công bội q = 2. Tính u₅.",
            (
                ("A", "80", True, None),
                ("B", "160", False, "dùng qⁿ thay cho qⁿ⁻¹"),
                ("C", "13", False, "cộng như cấp số cộng"),
                ("D", "40", False, "dùng qⁿ⁻²"),
            ),
            (
                ("Công thức", "uₙ = u₁ · qⁿ⁻¹ = 5 · 2⁴ = 80."),
                ("Nhân dần", "5, 10, 20, 40, 80."),
            ),
        ),
        Twin(
            "Cấp số nhân có u₁ = 1 và công bội q = 3. Tính u₅.",
            (
                ("A", "81", True, None),
                ("B", "243", False, "dùng qⁿ thay cho qⁿ⁻¹"),
                ("C", "13", False, "cộng như cấp số cộng"),
                ("D", "27", False, "dùng qⁿ⁻²"),
            ),
            (
                ("Công thức", "uₙ = u₁ · qⁿ⁻¹ = 3⁴ = 81."),
                ("Nhân dần", "1, 3, 9, 27, 81."),
            ),
        ),
    ),
    "Tính tổng 10 số hạng đầu của cấp số cộng có u₁ = 1 và d = 2.": (
        Twin(
            "Tính tổng 6 số hạng đầu của cấp số cộng có u₁ = 2 và d = 3.",
            (
                ("A", "57", True, None),
                ("B", "17", False, "chỉ tính u₆"),
                ("C", "66", False, "dùng u₆ = u₁ + 6d"),
                ("D", "114", False, "quên chia cho 2"),
            ),
            (
                ("Công thức", "u₆ = 17, S₆ = 6 · (2 + 17)/2 = 57."),
                ("Cộng trực tiếp", "2 + 5 + 8 + 11 + 14 + 17 = 57."),
            ),
        ),
        Twin(
            "Tính tổng 12 số hạng đầu của cấp số cộng có u₁ = 5 và d = 1.",
            (
                ("A", "126", True, None),
                ("B", "16", False, "chỉ tính u₁₂"),
                ("C", "132", False, "dùng u₁₂ = u₁ + 12d"),
                ("D", "252", False, "quên chia cho 2"),
            ),
            (
                ("Công thức", "u₁₂ = 16, S₁₂ = 12 · (5 + 16)/2 = 126."),
                ("Ghép cặp", "Sáu cặp, mỗi cặp số đầu cộng số cuối bằng 21."),
            ),
        ),
    ),
    "Dãy số nào sau đây là cấp số cộng?": (
        Twin(
            "Trong các dãy sau, dãy nào là cấp số cộng?",
            (
                ("A", "10; 7; 4; 1", True, None),
                ("B", "2; 6; 18; 54", False, "nhầm cấp số nhân với cấp số cộng"),
                ("C", "1; 2; 4; 7", False, "thấy dãy tăng là tưởng cấp số cộng"),
                ("D", "3; 5; 7; 10", False, "chỉ xét hai hiệu đầu"),
            ),
            (
                ("Hiệu liên tiếp", "10; 7; 4; 1 có mọi hiệu bằng −3."),
                ("Trung bình cộng", "Mỗi số hạng giữa bằng trung bình cộng hai số hạng kề."),
            ),
        ),
        Twin(
            "Trong các dãy sau, dãy nào là cấp số nhân?",
            (
                ("A", "1; −2; 4; −8", True, None),
                ("B", "1; 3; 5; 7", False, "nhầm cấp số cộng với cấp số nhân"),
                ("C", "1; 4; 9; 16", False, "thấy dãy tăng là tưởng cấp số nhân"),
                ("D", "2; 4; 8; 10", False, "chỉ xét hai số hạng đầu"),
            ),
            (
                ("Thương liên tiếp", "1; −2; 4; −8 có mọi thương bằng −2."),
                ("Trung bình nhân", "Bình phương số hạng giữa bằng tích hai số hạng kề."),
            ),
        ),
    ),
    "Tính tổng 4 số hạng đầu của cấp số nhân có u₁ = 1 và q = 2.": (
        Twin(
            "Tính tổng 5 số hạng đầu của cấp số nhân có u₁ = 1 và q = 3.",
            (
                ("A", "121", True, None),
                ("B", "243", False, "lấy u₁ · qⁿ"),
                ("C", "81", False, "chỉ tính u₅"),
                ("D", "364", False, "cộng thừa một số hạng"),
            ),
            (
                ("Công thức", "S₅ = (3⁵ − 1)/(3 − 1) = 242/2 = 121."),
                ("Cộng trực tiếp", "1 + 3 + 9 + 27 + 81 = 121."),
            ),
        ),
        Twin(
            "Tính tổng 4 số hạng đầu của cấp số nhân có u₁ = 3 và q = 2.",
            (
                ("A", "45", True, None),
                ("B", "48", False, "lấy u₁ · qⁿ"),
                ("C", "24", False, "chỉ tính u₄"),
                ("D", "93", False, "cộng thừa một số hạng"),
            ),
            (
                ("Công thức", "S₄ = 3(2⁴ − 1)/(2 − 1) = 45."),
                ("Cộng trực tiếp", "3 + 6 + 12 + 24 = 45."),
            ),
        ),
    ),
    "Ba số x; 5; 9 theo thứ tự lập thành cấp số cộng. Tìm x.": (
        Twin(
            "Ba số 3; x; 11 theo thứ tự lập thành cấp số cộng. Tìm x.",
            (
                ("A", "7", True, None),
                ("B", "14", False, "cộng hai số hạng mà quên chia đôi"),
                ("C", "4", False, "lấy công sai làm số hạng"),
                ("D", "−7", False, "sai dấu khi chuyển vế"),
            ),
            (
                ("Số hạng giữa", "x = (3 + 11)/2 = 7."),
                ("Công sai", "2d = 11 − 3 = 8, d = 4, nên x = 3 + 4 = 7."),
            ),
        ),
        Twin(
            "Ba số dương 3; x; 27 theo thứ tự lập thành cấp số nhân. Tìm x.",
            (
                ("A", "9", True, None),
                ("B", "15", False, "dùng trung bình cộng thay cho trung bình nhân"),
                ("C", "81", False, "nhân hai số hạng mà quên lấy căn"),
                ("D", "24", False, "lấy hiệu hai số hạng"),
            ),
            (
                ("Số hạng giữa", "x² = 3 · 27 = 81, x dương nên x = 9."),
                ("Công bội", "q² = 27/3 = 9, q = 3, nên x = 3 · 3 = 9."),
            ),
        ),
    ),
    # ------------------------------------------------------------------ Hàm số (bộ demo)
    "Đạo hàm của y = x² + 3x là gì?": (
        Twin(
            "Đạo hàm của y = x⁴ + x² là gì?",
            (
                ("A", "4x³ + 2x", True, None),
                ("B", "x³ + x", False, "quên nhân số mũ khi hạ bậc"),
                ("C", "4x³", False, "bỏ sót đạo hàm của số hạng bậc hai"),
                ("D", "x⁴ + 2x", False, "chỉ đạo hàm một số hạng"),
            ),
            (
                ("Công thức luỹ thừa", "(xⁿ)′ = n·xⁿ⁻¹: (x⁴)′ = 4x³, (x²)′ = 2x."),
                ("Kiểm bằng một điểm", "Tại x = 1, hệ số góc tiếp tuyến bằng 4 + 2 = 6."),
            ),
        ),
        Twin(
            "Đạo hàm của y = 2x³ + 5x là gì?",
            (
                ("A", "6x² + 5", True, None),
                ("B", "2x² + 5", False, "quên nhân số mũ khi hạ bậc"),
                ("C", "6x²", False, "bỏ sót đạo hàm của số hạng bậc nhất"),
                ("D", "2x³ + 5", False, "chỉ đạo hàm một số hạng"),
            ),
            (
                ("Công thức luỹ thừa", "(2x³)′ = 6x², (5x)′ = 5."),
                ("Kiểm bằng một điểm", "Tại x = 1, hệ số góc tiếp tuyến bằng 6 + 5 = 11."),
            ),
        ),
    ),
    "Hàm số y = 2x + 1 đồng biến trên khoảng nào?": (
        Twin(
            "Hàm số y = 5x − 4 đồng biến trên khoảng nào?",
            (
                ("A", "Khoảng (−∞; +∞)", True, None),
                ("B", "Khoảng (0; +∞)", False, "tưởng hàm bậc nhất chỉ tăng khi x dương"),
                ("C", "Khoảng (−∞; 0)", False, "đọc ngược chiều biến thiên"),
                ("D", "Không đồng biến ở đâu", False, "nhầm hệ số góc dương với hàm hằng"),
            ),
            (
                ("Hệ số góc", "y′ = 5 > 0 với mọi x, nên hàm đồng biến trên toàn trục số."),
                ("Đồ thị", "Đường thẳng có hệ số góc dương đi lên trên toàn miền xác định."),
            ),
        ),
        Twin(
            "Hàm số y = −x + 7 nghịch biến trên khoảng nào?",
            (
                ("A", "Khoảng (−∞; +∞)", True, None),
                ("B", "Khoảng (0; +∞)", False, "tưởng hàm bậc nhất chỉ giảm khi x dương"),
                ("C", "Khoảng (−∞; 0)", False, "đọc ngược chiều biến thiên"),
                ("D", "Không nghịch biến ở đâu", False, "nhầm hệ số góc âm với hàm hằng"),
            ),
            (
                ("Hệ số góc", "y′ = −1 < 0 với mọi x, nên hàm nghịch biến trên toàn trục số."),
                ("Đồ thị", "Đường thẳng có hệ số góc âm đi xuống trên toàn miền xác định."),
            ),
        ),
    ),
    "Giới hạn của (x² − 1)/(x − 1) khi x → 1 bằng bao nhiêu?": (
        Twin(
            "Giới hạn của (x² − 9)/(x − 3) khi x → 3 bằng bao nhiêu?",
            (
                ("A", "6", True, None),
                ("B", "0", False, "thay thẳng x = 3 vào tử rồi dừng"),
                ("C", "3", False, "rút gọn sai khi phân tích hiệu hai bình phương"),
                ("D", "Không tồn tại", False, "coi dạng 0/0 là không có giới hạn"),
            ),
            (
                ("Phân tích thành nhân tử", "(x² − 9) = (x − 3)(x + 3), rút gọn rồi thay x = 3."),
                ("Quy tắc L'Hôpital", "Đạo hàm tử và mẫu: 2x / 1, thay x = 3 được 6."),
            ),
        ),
        Twin(
            "Giới hạn của (x² − 16)/(x + 4) khi x → −4 bằng bao nhiêu?",
            (
                ("A", "−8", True, None),
                ("B", "0", False, "thay thẳng x = −4 vào tử rồi dừng"),
                ("C", "−4", False, "rút gọn sai khi phân tích hiệu hai bình phương"),
                ("D", "Không tồn tại", False, "coi dạng 0/0 là không có giới hạn"),
            ),
            (
                ("Phân tích thành nhân tử", "(x² − 16) = (x + 4)(x − 4), rút gọn rồi thay x = −4."),
                ("Quy tắc L'Hôpital", "Đạo hàm tử và mẫu: 2x / 1, thay x = −4 được −8."),
            ),
        ),
    ),
    "Cho hàm số y = x³ − 3x. Hàm số đồng biến trên khoảng nào?": (
        Twin(
            "Cho hàm số y = x³ − 27x. Hàm số đồng biến trên khoảng nào?",
            (
                ("A", "Khoảng (3; +∞)", True, None),
                ("B", "Khoảng (−3; 3)", False, "đọc ngược khoảng đồng biến và nghịch biến"),
                ("C", "Khoảng (0; 4)", False, "chỉ thử một điểm rồi suy ra cả khoảng"),
                ("D", "Khoảng (2; 5)", False, "lấy khoảng chứa cả phần tăng lẫn phần giảm"),
            ),
            (
                ("Xét dấu đạo hàm", "y′ = 3x² − 27 > 0 khi x < −3 hoặc x > 3."),
                ("Bảng biến thiên", "Lập bảng với hai điểm tới hạn x = ±3 rồi đọc chiều."),
            ),
        ),
        Twin(
            "Cho hàm số y = −x³ + 3x. Hàm số đồng biến trên khoảng nào?",
            (
                ("A", "Khoảng (−1; 1)", True, None),
                ("B", "Khoảng (1; +∞)", False, "đọc ngược khoảng đồng biến và nghịch biến"),
                ("C", "Khoảng (0; 2)", False, "chỉ thử một điểm rồi suy ra cả khoảng"),
                ("D", "Khoảng (−2; 0)", False, "lấy khoảng chứa cả phần tăng lẫn phần giảm"),
            ),
            (
                ("Xét dấu đạo hàm", "y′ = −3x² + 3 > 0 khi −1 < x < 1."),
                ("Bảng biến thiên", "Lập bảng với hai điểm tới hạn x = ±1 rồi đọc chiều."),
            ),
        ),
    ),
    "Đồ thị y = (2x − 1)/(x + 3) có tiệm cận ngang là đường nào?": (
        Twin(
            "Đồ thị y = (4x − 3)/(2x + 1) có tiệm cận ngang là đường nào?",
            (
                ("A", "y = 2", True, None),
                ("B", "x = −1/2", False, "nhầm tiệm cận đứng với tiệm cận ngang"),
                ("C", "y = −3", False, "lấy tỉ số hai hằng số thay vì hai hệ số bậc cao nhất"),
                ("D", "y = 0", False, "áp quy tắc của trường hợp bậc tử nhỏ hơn bậc mẫu"),
            ),
            (
                ("Tỉ số hệ số bậc cao nhất", "Bậc tử bằng bậc mẫu nên tiệm cận ngang là 4/2 = 2."),
                ("Lấy giới hạn", "Cho x → ±∞, chia cả tử và mẫu cho x rồi lấy giới hạn."),
            ),
        ),
        Twin(
            "Đồ thị y = (x + 5)/(x − 2) có tiệm cận ngang là đường nào?",
            (
                ("A", "y = 1", True, None),
                ("B", "x = 2", False, "nhầm tiệm cận đứng với tiệm cận ngang"),
                ("C", "y = −5/2", False, "lấy tỉ số hai hằng số thay vì hai hệ số bậc cao nhất"),
                ("D", "y = 0", False, "áp quy tắc của trường hợp bậc tử nhỏ hơn bậc mẫu"),
            ),
            (
                ("Tỉ số hệ số bậc cao nhất", "Bậc tử bằng bậc mẫu nên tiệm cận ngang là 1/1 = 1."),
                ("Lấy giới hạn", "Cho x → ±∞, chia cả tử và mẫu cho x rồi lấy giới hạn."),
            ),
        ),
    ),
    "Giá trị nhỏ nhất của y = x + 4/x trên (0; +∞) bằng bao nhiêu?": (
        Twin(
            "Giá trị nhỏ nhất của y = x + 16/x trên (0; +∞) bằng bao nhiêu?",
            (
                ("A", "8", True, None),
                ("B", "1", False, "lấy hệ số của x thay cho giá trị nhỏ nhất"),
                ("C", "4", False, "lấy giá trị của x tại điểm cực tiểu thay cho giá trị của y"),
                ("D", "0", False, "coi hàm giảm mãi nên không có giá trị nhỏ nhất dương"),
            ),
            (
                ("Đạo hàm", "y′ = 1 − 16/x² = 0 cho x = 4, thay lại được y(4) = 8."),
                ("Bất đẳng thức Cô-si", "x + 16/x ≥ 2√16 = 8 với x > 0, dấu bằng khi x = 4."),
            ),
        ),
        Twin(
            "Giá trị nhỏ nhất của y = x + 25/x trên (0; +∞) bằng bao nhiêu?",
            (
                ("A", "10", True, None),
                ("B", "1", False, "lấy hệ số của x thay cho giá trị nhỏ nhất"),
                ("C", "5", False, "lấy giá trị của x tại điểm cực tiểu thay cho giá trị của y"),
                ("D", "0", False, "coi hàm giảm mãi nên không có giá trị nhỏ nhất dương"),
            ),
            (
                ("Đạo hàm", "y′ = 1 − 25/x² = 0 cho x = 5, thay lại được y(5) = 10."),
                ("Bất đẳng thức Cô-si", "x + 25/x ≥ 2√25 = 10 với x > 0, dấu bằng khi x = 5."),
            ),
        ),
    ),
    # ------------------------------------------------------------------ Mũ và logarit
    "log₂ 8 bằng bao nhiêu?": (
        Twin(
            "log₅ 125 bằng bao nhiêu?",
            (
                ("A", "3", True, None),
                ("B", "25", False, "chia 125 cho cơ số"),
                ("C", "5¹²⁵", False, "nhầm logarit với luỹ thừa"),
                ("D", "1/3", False, "đảo ngược kết quả"),
            ),
            (
                ("Định nghĩa", "log₅ 125 = x nghĩa là 5ˣ = 125, nên x = 3."),
                ("Viết thành luỹ thừa", "125 = 5³, nên log₅ 5³ = 3."),
            ),
        ),
        Twin(
            "log₂ 32 bằng bao nhiêu?",
            (
                ("A", "5", True, None),
                ("B", "16", False, "chia 32 cho cơ số"),
                ("C", "2³²", False, "nhầm logarit với luỹ thừa"),
                ("D", "1/5", False, "đảo ngược kết quả"),
            ),
            (
                ("Định nghĩa", "log₂ 32 = x nghĩa là 2ˣ = 32, nên x = 5."),
                ("Viết thành luỹ thừa", "32 = 2⁵, nên log₂ 2⁵ = 5."),
            ),
        ),
    ),
    "Rút gọn 2³ · 2⁴.": (
        Twin(
            "Rút gọn 5² · 5⁶.",
            (
                ("A", "5⁸", True, None),
                ("B", "5¹²", False, "nhân số mũ thay vì cộng"),
                ("C", "25⁸", False, "nhân cả hai cơ số"),
                ("D", "5⁴", False, "trừ số mũ khi nhân"),
            ),
            (
                ("Quy tắc", "aᵐ · aⁿ = aᵐ⁺ⁿ, nên 5² · 5⁶ = 5⁸."),
                ("Kiểm lại", "5⁸ : 5⁶ = 5², đúng thừa số còn lại."),
            ),
        ),
        Twin(
            "Rút gọn 7⁹ : 7⁴.",
            (
                ("A", "7⁵", True, None),
                ("B", "7³⁶", False, "nhân số mũ thay vì trừ"),
                ("C", "1⁵", False, "chia cả hai cơ số"),
                ("D", "7¹³", False, "cộng số mũ khi chia"),
            ),
            (
                ("Quy tắc", "aᵐ : aⁿ = aᵐ⁻ⁿ, nên 7⁹ : 7⁴ = 7⁵."),
                ("Kiểm lại", "7⁵ · 7⁴ = 7⁹."),
            ),
        ),
    ),
    "Tập xác định của hàm số y = log(x − 2) là tập nào?": (
        Twin(
            "Tập xác định của hàm số y = log₃(x + 1) là tập nào?",
            (
                ("A", "(−1; +∞)", True, None),
                ("B", "[−1; +∞)", False, "cho biểu thức trong logarit bằng 0"),
                ("C", "ℝ", False, "quên điều kiện của logarit"),
                ("D", "(−∞; −1)", False, "giải ngược chiều bất phương trình"),
            ),
            (
                ("Điều kiện", "Biểu thức trong logarit phải dương: x + 1 > 0, tức x > −1."),
                ("Thử điểm", "x = −1 làm log₃ 0 vô nghĩa, nên đầu mút −1 bị loại."),
            ),
        ),
        Twin(
            "Tập xác định của hàm số y = ln(5 − x) là tập nào?",
            (
                ("A", "(−∞; 5)", True, None),
                ("B", "(−∞; 5]", False, "cho biểu thức trong logarit bằng 0"),
                ("C", "ℝ", False, "quên điều kiện của logarit"),
                ("D", "(5; +∞)", False, "giải ngược chiều bất phương trình"),
            ),
            (
                ("Điều kiện", "Biểu thức trong logarit phải dương: 5 − x > 0, tức x < 5."),
                ("Thử điểm", "x = 5 làm ln 0 vô nghĩa, nên đầu mút 5 bị loại."),
            ),
        ),
    ),
    "Nghiệm của phương trình 2ˣ = 16 là gì?": (
        Twin(
            "Nghiệm của phương trình 3ˣ = 27 là gì?",
            (
                ("A", "x = 3", True, None),
                ("B", "x = 9", False, "chia 27 cho cơ số"),
                ("C", "x = √27", False, "lấy căn bậc hai"),
                ("D", "x = 81", False, "nhân 27 với cơ số"),
            ),
            (
                ("Cùng cơ số", "27 = 3³, nên 3ˣ = 3³ và x = 3."),
                ("Lấy logarit", "x = log₃ 27 = 3."),
            ),
        ),
        Twin(
            "Nghiệm của phương trình 5ˣ⁺¹ = 25 là gì?",
            (
                ("A", "x = 1", True, None),
                ("B", "x = 2", False, "quên cộng 1 ở số mũ"),
                ("C", "x = 3", False, "cộng 1 thay vì trừ khi chuyển vế"),
                ("D", "x = 24", False, "trừ 1 vào 25"),
            ),
            (
                ("Cùng cơ số", "25 = 5², nên x + 1 = 2 và x = 1."),
                ("Lấy logarit", "x + 1 = log₅ 25 = 2."),
            ),
        ),
    ),
    "Tính log 2 + log 5.": (
        Twin(
            "Tính log₆ 4 + log₆ 9.",
            (
                ("A", "2", True, None),
                ("B", "log₆ 13", False, "cộng hai biểu thức trong logarit"),
                ("C", "36", False, "quên lấy logarit của tích"),
                ("D", "log₆ 4 · log₆ 9", False, "nhầm tổng thành tích"),
            ),
            (
                ("Quy tắc", "log a + log b = log(ab) = log₆ 36 = 2."),
                ("Kiểm lại", "6² = 36 = 4 · 9."),
            ),
        ),
        Twin(
            "Tính log₃ 54 − log₃ 2.",
            (
                ("A", "3", True, None),
                ("B", "log₃ 52", False, "trừ hai biểu thức trong logarit"),
                ("C", "27", False, "quên lấy logarit của thương"),
                ("D", "log₃ 108", False, "nhầm hiệu thành tích"),
            ),
            (
                ("Quy tắc", "log a − log b = log(a/b) = log₃ 27 = 3."),
                ("Kiểm lại", "3³ = 27 = 54 : 2."),
            ),
        ),
    ),
    "Hàm số nào sau đây đồng biến trên ℝ?": (
        Twin(
            "Trong bốn hàm số dưới đây, hàm nào đồng biến trên ℝ?",
            (
                ("A", "y = 5ˣ", True, None),
                ("B", "y = (1/5)ˣ", False, "quên rằng cơ số nhỏ hơn 1 thì nghịch biến"),
                ("C", "y = log₅ x", False, "quên tập xác định chỉ là (0; +∞)"),
                ("D", "y = x⁴", False, "coi mọi hàm luỹ thừa đều đồng biến"),
            ),
            (
                ("Theo cơ số", "y = aˣ đồng biến trên ℝ khi a > 1; ở đây a = 5."),
                ("Tập xác định", "Đồng biến trên ℝ thì trước hết phải xác định trên ℝ."),
            ),
        ),
        Twin(
            "Trong bốn hàm số dưới đây, hàm nào nghịch biến trên ℝ?",
            (
                ("A", "y = (2/3)ˣ", True, None),
                ("B", "y = (3/2)ˣ", False, "quên rằng cơ số lớn hơn 1 thì đồng biến"),
                ("C", "y = log₂/₃ x", False, "quên tập xác định chỉ là (0; +∞)"),
                ("D", "y = −x⁴", False, "coi mọi hàm có dấu trừ đều nghịch biến"),
            ),
            (
                ("Theo cơ số", "y = aˣ nghịch biến trên ℝ khi 0 < a < 1; ở đây a = 2/3."),
                ("Tập xác định", "Nghịch biến trên ℝ thì trước hết phải xác định trên ℝ."),
            ),
        ),
    ),
}


def twins(item: Item) -> tuple[Twin, Twin, Twin]:
    """Ba đề của ba vòng chữa cho `item`, theo thứ tự vòng.

    Args:
        item: Một câu trong `papers.TOPICS`.

    Returns:
        Đề vòng 1 (`item.twin`), rồi hai đề ở đây.
    """
    second, third = _MORE[item.stem]
    return (item.twin, second, third)
