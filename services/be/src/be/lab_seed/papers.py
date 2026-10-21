"""Sáu bộ câu Toán viết tay cho seed lab: hai bộ mỗi khối 10, 11, 12.

Mỗi câu có bốn phương án, đúng một phương án đúng, mỗi phương án sai mang nhãn lỗi (ADR-18), hai
cách giải, và một **câu song sinh** -- cùng mục kiến thức, cùng kiểu lỗi, khác số -- làm câu của
vòng chữa (`RoundItem`). Không gọi model: chạy lại seed ra đúng những chữ này.

Bộ *Hàm số* của khối 12 là đúng sáu câu của dữ liệu demo (`be.seed.DEMO_QUESTIONS`), để người đã
quen demo nhận ra; chỉ phần song sinh là mới.
"""

from dataclasses import dataclass

from be.seed import DEMO_QUESTIONS

# (nhãn, nội dung, đúng?, nhãn lỗi)
Option = tuple[str, str, bool, str | None]
# (tên cách làm, các bước)
Method = tuple[str, str]


@dataclass(frozen=True)
class Twin:
    """Câu của vòng chữa cho một câu gốc.

    Attributes:
        stem: Đề bài.
        options: Bốn phương án.
        methods: Cách giải riêng của câu này; rỗng thì dùng cách giải của câu gốc.
    """

    stem: str
    options: tuple[Option, ...]
    methods: tuple[Method, ...] = ()


@dataclass(frozen=True)
class Item:
    """Một câu của đề.

    Attributes:
        stem: Đề bài.
        objective: Mục kiến thức (`Question.learning_objective`).
        options: Bốn phương án.
        methods: Hai cách giải.
        twin: Câu song sinh cho vòng chữa.
    """

    stem: str
    objective: str
    options: tuple[Option, ...]
    methods: tuple[Method, ...]
    twin: Twin


@dataclass(frozen=True)
class Topic:
    """Một bộ sáu câu.

    Attributes:
        grade: Khối, `"10"` … `"12"`.
        name: Tên chủ đề, ghép vào tên đề.
        items: Sáu câu.
    """

    grade: str
    name: str
    items: tuple[Item, ...]


_QUADRATIC = Topic(
    "10",
    "Hàm số bậc hai",
    (
        Item(
            "Đỉnh của parabol y = x² − 4x + 3 là điểm nào?",
            "Đỉnh của parabol",
            (
                ("A", "(2; −1)", True, None),
                ("B", "(−2; 15)", False, "đổi dấu hoành độ đỉnh"),
                ("C", "(2; 3)", False, "lấy hệ số tự do làm tung độ đỉnh"),
                ("D", "(4; 3)", False, "dùng −b/a thay cho −b/(2a)"),
            ),
            (
                ("Công thức đỉnh", "Hoành độ đỉnh x = −b/(2a), thay lại vào hàm để được tung độ."),
                ("Đưa về dạng bình phương", "Viết y = a(x − p)² + q rồi đọc đỉnh (p; q)."),
            ),
            Twin(
                "Đỉnh của parabol y = x² + 2x − 3 là điểm nào?",
                (
                    ("A", "(−1; −4)", True, None),
                    ("B", "(1; 0)", False, "đổi dấu hoành độ đỉnh"),
                    ("C", "(−1; −3)", False, "lấy hệ số tự do làm tung độ đỉnh"),
                    ("D", "(−2; −3)", False, "dùng −b/a thay cho −b/(2a)"),
                ),
            ),
        ),
        Item(
            "Trục đối xứng của parabol y = 2x² − 8x + 1 là đường nào?",
            "Trục đối xứng của parabol",
            (
                ("A", "x = 2", True, None),
                ("B", "x = −2", False, "sai dấu trong công thức −b/(2a)"),
                ("C", "x = 4", False, "dùng −b/a thay cho −b/(2a)"),
                ("D", "y = 2", False, "nhầm trục đối xứng với một đường nằm ngang"),
            ),
            (
                ("Công thức", "Trục đối xứng là đường thẳng đứng x = −b/(2a)."),
                (
                    "Hai điểm đối xứng",
                    "Hai điểm cùng tung độ nằm đối xứng qua trục; lấy trung điểm.",
                ),
            ),
            Twin(
                "Trục đối xứng của parabol y = −x² + 6x là đường nào?",
                (
                    ("A", "x = 3", True, None),
                    ("B", "x = −3", False, "sai dấu trong công thức −b/(2a)"),
                    ("C", "x = 6", False, "dùng −b/a thay cho −b/(2a)"),
                    ("D", "y = 3", False, "nhầm trục đối xứng với một đường nằm ngang"),
                ),
            ),
        ),
        Item(
            "Hàm số y = −x² + 2x + 3 đồng biến trên khoảng nào?",
            "Chiều biến thiên của hàm bậc hai",
            (
                ("A", "(−∞; 1)", True, None),
                ("B", "(1; +∞)", False, "quên rằng a < 0 làm đảo chiều biến thiên"),
                ("C", "(−1; 3)", False, "lấy khoảng giữa hai nghiệm"),
                ("D", "(−∞; 3)", False, "lấy nghiệm làm mốc thay cho hoành độ đỉnh"),
            ),
            (
                ("Theo dấu của a", "a < 0: tăng bên trái đỉnh, giảm bên phải; đỉnh tại x = 1."),
                ("Bảng biến thiên", "Lập bảng biến thiên quanh hoành độ đỉnh rồi đọc chiều."),
            ),
            Twin(
                "Hàm số y = x² − 6x + 5 nghịch biến trên khoảng nào?",
                (
                    ("A", "(−∞; 3)", True, None),
                    ("B", "(3; +∞)", False, "quên rằng chiều biến thiên đi theo dấu của a"),
                    ("C", "(1; 5)", False, "lấy khoảng giữa hai nghiệm"),
                    ("D", "(−∞; 5)", False, "lấy nghiệm làm mốc thay cho hoành độ đỉnh"),
                ),
            ),
        ),
        Item(
            "Giá trị nhỏ nhất của hàm số y = x² − 2x + 5 bằng bao nhiêu?",
            "Giá trị lớn nhất, nhỏ nhất của hàm bậc hai",
            (
                ("A", "4", True, None),
                ("B", "1", False, "lấy hoành độ đỉnh thay cho giá trị nhỏ nhất"),
                ("C", "5", False, "lấy hệ số tự do"),
                ("D", "0", False, "nghĩ parabol nào cũng chạm trục hoành"),
            ),
            (
                ("Tung độ đỉnh", "a > 0 nên giá trị nhỏ nhất là tung độ đỉnh: y(1) = 4."),
                ("Hằng đẳng thức", "y = (x − 1)² + 4 ≥ 4, dấu bằng khi x = 1."),
            ),
            Twin(
                "Giá trị nhỏ nhất của hàm số y = x² + 4x + 7 bằng bao nhiêu?",
                (
                    ("A", "3", True, None),
                    ("B", "−2", False, "lấy hoành độ đỉnh thay cho giá trị nhỏ nhất"),
                    ("C", "7", False, "lấy hệ số tự do"),
                    ("D", "0", False, "nghĩ parabol nào cũng chạm trục hoành"),
                ),
            ),
        ),
        Item(
            "Parabol y = x² − 5x + 6 cắt trục hoành tại những điểm có hoành độ nào?",
            "Giao điểm của parabol với trục hoành",
            (
                ("A", "x = 2 và x = 3", True, None),
                ("B", "x = −2 và x = −3", False, "đổi dấu nghiệm"),
                ("C", "x = 1 và x = 6", False, "phân tích sai thành nhân tử"),
                ("D", "Không cắt", False, "tính sai biệt thức"),
            ),
            (
                ("Giải phương trình", "Cho y = 0: x² − 5x + 6 = 0, Δ = 1 > 0, hai nghiệm 2 và 3."),
                ("Định lí Vi-ét", "Tìm hai số có tổng 5 và tích 6."),
            ),
            Twin(
                "Parabol y = x² − x − 6 cắt trục hoành tại những điểm có hoành độ nào?",
                (
                    ("A", "x = −2 và x = 3", True, None),
                    ("B", "x = 2 và x = −3", False, "đổi dấu nghiệm"),
                    ("C", "x = 1 và x = −6", False, "phân tích sai thành nhân tử"),
                    ("D", "Không cắt", False, "tính sai biệt thức"),
                ),
            ),
        ),
        Item(
            "Parabol y = ax² + bx + c có đỉnh (2; 0) và đi qua (0; 12). Hệ số a bằng bao nhiêu?",
            "Xác định parabol từ đỉnh và một điểm",
            (
                ("A", "3", True, None),
                ("B", "−3", False, "sai dấu khi thay toạ độ điểm"),
                ("C", "6", False, "quên bình phương khoảng cách tới đỉnh"),
                ("D", "12", False, "lấy tung độ giao điểm với trục tung làm a"),
            ),
            (
                ("Dạng đỉnh", "y = a(x − 2)²; thay (0; 12) được 4a = 12, nên a = 3."),
                ("Hệ phương trình", "Lập hệ từ c = 12, −b/(2a) = 2 và y(2) = 0 rồi giải."),
            ),
            Twin(
                "Parabol y = ax² + bx + c có đỉnh (3; 0), đi qua (0; 18). Hệ số a bằng bao nhiêu?",
                (
                    ("A", "2", True, None),
                    ("B", "−2", False, "sai dấu khi thay toạ độ điểm"),
                    ("C", "6", False, "quên bình phương khoảng cách tới đỉnh"),
                    ("D", "18", False, "lấy tung độ giao điểm với trục tung làm a"),
                ),
            ),
        ),
    ),
)

_SETS = Topic(
    "10",
    "Mệnh đề và tập hợp",
    (
        Item(
            "Mệnh đề phủ định của “∀x ∈ ℝ, x² ≥ 0” là mệnh đề nào?",
            "Phủ định mệnh đề có lượng từ",
            (
                ("A", "∃x ∈ ℝ, x² < 0", True, None),
                ("B", "∀x ∈ ℝ, x² < 0", False, "giữ nguyên lượng từ ∀"),
                ("C", "∃x ∈ ℝ, x² ≥ 0", False, "đổi lượng từ nhưng quên phủ định vế sau"),
                ("D", "∀x ∈ ℝ, x² ≤ 0", False, "phủ định ≥ thành ≤"),
            ),
            (
                ("Hai bước", "Đổi ∀ thành ∃, rồi phủ định tính chất: ≥ thành <."),
                ("Kiểm bằng nghĩa", "Mệnh đề gốc sai khi có ít nhất một x làm x² < 0."),
            ),
            Twin(
                "Mệnh đề phủ định của “∃x ∈ ℝ, x² + 1 = 0” là mệnh đề nào?",
                (
                    ("A", "∀x ∈ ℝ, x² + 1 ≠ 0", True, None),
                    ("B", "∃x ∈ ℝ, x² + 1 ≠ 0", False, "giữ nguyên lượng từ ∃"),
                    ("C", "∀x ∈ ℝ, x² + 1 = 0", False, "đổi lượng từ nhưng quên phủ định vế sau"),
                    ("D", "∃x ∈ ℝ, x² + 1 > 0", False, "phủ định = thành >"),
                ),
            ),
        ),
        Item(
            "Cho A = {1; 2; 3; 4} và B = {3; 4; 5}. Tập A ∩ B là tập nào?",
            "Giao của hai tập hợp",
            (
                ("A", "{3; 4}", True, None),
                ("B", "{1; 2; 3; 4; 5}", False, "nhầm giao với hợp"),
                ("C", "{1; 2}", False, "lấy A \\ B"),
                ("D", "{5}", False, "lấy B \\ A"),
            ),
            (
                ("Theo định nghĩa", "A ∩ B gồm các phần tử thuộc cả A lẫn B."),
                ("Biểu đồ Ven", "Vẽ hai vòng tròn, phần chung là giao."),
            ),
            Twin(
                "Cho A = {2; 4; 6; 8} và B = {4; 8; 10}. Tập A ∩ B là tập nào?",
                (
                    ("A", "{4; 8}", True, None),
                    ("B", "{2; 4; 6; 8; 10}", False, "nhầm giao với hợp"),
                    ("C", "{2; 6}", False, "lấy A \\ B"),
                    ("D", "{10}", False, "lấy B \\ A"),
                ),
            ),
        ),
        Item(
            "Cho A = [1; 5) và B = (3; 7]. Tập A ∪ B là tập nào?",
            "Hợp của hai khoảng",
            (
                ("A", "[1; 7]", True, None),
                ("B", "(3; 5)", False, "nhầm hợp với giao"),
                ("C", "[1; 3]", False, "lấy A \\ B"),
                ("D", "[1; 7)", False, "đọc sai đầu mút của B"),
            ),
            (
                ("Trục số", "Tô cả hai khoảng trên trục số, hợp là toàn bộ phần đã tô."),
                ("Đầu mút", "Đầu mút trái lấy của A (đóng), đầu mút phải lấy của B (đóng)."),
            ),
            Twin(
                "Cho A = (−2; 4] và B = [1; 6). Tập A ∪ B là tập nào?",
                (
                    ("A", "(−2; 6)", True, None),
                    ("B", "[1; 4]", False, "nhầm hợp với giao"),
                    ("C", "(−2; 1)", False, "lấy A \\ B"),
                    ("D", "(−2; 6]", False, "đọc sai đầu mút của B"),
                ),
            ),
        ),
        Item(
            "Tập {a; b; c} có bao nhiêu tập con?",
            "Số tập con của một tập hữu hạn",
            (
                ("A", "8", True, None),
                ("B", "6", False, "quên tập rỗng và chính tập đó"),
                ("C", "7", False, "quên tập rỗng"),
                ("D", "3", False, "chỉ đếm tập con một phần tử"),
            ),
            (
                ("Công thức", "Tập có n phần tử có 2ⁿ tập con; ở đây 2³ = 8."),
                ("Liệt kê", "Đếm theo số phần tử: 1 + 3 + 3 + 1 = 8."),
            ),
            Twin(
                "Tập {1; 2; 3; 4} có bao nhiêu tập con?",
                (
                    ("A", "16", True, None),
                    ("B", "14", False, "quên tập rỗng và chính tập đó"),
                    ("C", "15", False, "quên tập rỗng"),
                    ("D", "4", False, "chỉ đếm tập con một phần tử"),
                ),
            ),
        ),
        Item(
            "Mệnh đề nào sau đây đúng?",
            "Xét tính đúng sai của mệnh đề",
            (
                ("A", "√2 là số vô tỉ", True, None),
                ("B", "√4 là số vô tỉ", False, "không rút gọn căn trước khi xét"),
                ("C", "−5 > −3", False, "so sánh số âm theo trị tuyệt đối"),
                ("D", "1/3 = 0,33", False, "nhầm giá trị gần đúng với giá trị đúng"),
            ),
            (
                ("Xét từng mệnh đề", "Tính hay rút gọn từng vế rồi so với định nghĩa."),
                ("Phản ví dụ", "Một mệnh đề sai chỉ cần một chỗ không khớp."),
            ),
            Twin(
                "Trong các mệnh đề sau, mệnh đề nào đúng?",
                (
                    ("A", "0 là số tự nhiên", True, None),
                    ("B", "√9 là số vô tỉ", False, "không rút gọn căn trước khi xét"),
                    ("C", "−7 > −2", False, "so sánh số âm theo trị tuyệt đối"),
                    ("D", "2/3 = 0,67", False, "nhầm giá trị gần đúng với giá trị đúng"),
                ),
            ),
        ),
        Item(
            "Cho A = {x ∈ ℝ | x² − 3x + 2 = 0}. Liệt kê các phần tử của A.",
            "Tập hợp cho bởi tính chất đặc trưng",
            (
                ("A", "{1; 2}", True, None),
                ("B", "{−1; −2}", False, "đổi dấu nghiệm"),
                ("C", "{3; 2}", False, "lấy hệ số làm phần tử"),
                ("D", "∅", False, "tính sai biệt thức"),
            ),
            (
                ("Giải phương trình", "x² − 3x + 2 = (x − 1)(x − 2) = 0."),
                ("Thử lại", "Thay từng giá trị tìm được vào phương trình."),
            ),
            Twin(
                "Cho A = {x ∈ ℝ | x² − 5x + 4 = 0}. Liệt kê các phần tử của A.",
                (
                    ("A", "{1; 4}", True, None),
                    ("B", "{−1; −4}", False, "đổi dấu nghiệm"),
                    ("C", "{5; 4}", False, "lấy hệ số làm phần tử"),
                    ("D", "∅", False, "tính sai biệt thức"),
                ),
            ),
        ),
    ),
)

_TRIGONOMETRY = Topic(
    "11",
    "Lượng giác",
    (
        Item(
            "Đổi 60° ra radian.",
            "Đổi đơn vị đo góc",
            (
                ("A", "π/3", True, None),
                ("B", "π/6", False, "nhầm 60° với 30°"),
                ("C", "3/π", False, "lật ngược tỉ số π/180"),
                ("D", "60π", False, "quên chia cho 180"),
            ),
            (
                ("Tỉ số", "Nhân số đo độ với π/180: 60 · π/180 = π/3."),
                ("Góc quen", "180° ứng với π, nên 60° là một phần ba của π."),
            ),
            Twin(
                "Đổi 135° ra radian.",
                (
                    ("A", "3π/4", True, None),
                    ("B", "π/4", False, "chỉ đổi phần 45°"),
                    ("C", "4/(3π)", False, "lật ngược tỉ số π/180"),
                    ("D", "135π", False, "quên chia cho 180"),
                ),
            ),
        ),
        Item(
            "sin(π/6) bằng bao nhiêu?",
            "Giá trị lượng giác của góc đặc biệt",
            (
                ("A", "1/2", True, None),
                ("B", "√3/2", False, "nhầm sin với cos"),
                ("C", "√2/2", False, "lấy giá trị của góc π/4"),
                ("D", "1", False, "nhầm với sin(π/2)"),
            ),
            (
                ("Đường tròn lượng giác", "Điểm ứng với π/6 có tung độ 1/2."),
                ("Tam giác nửa đều", "Cạnh đối diện góc 30° bằng nửa cạnh huyền."),
            ),
            Twin(
                "cos(π/3) bằng bao nhiêu?",
                (
                    ("A", "1/2", True, None),
                    ("B", "√3/2", False, "nhầm cos với sin"),
                    ("C", "√2/2", False, "lấy giá trị của góc π/4"),
                    ("D", "0", False, "nhầm với cos(π/2)"),
                ),
            ),
        ),
        Item(
            "Phương trình sin x = 0 có nghiệm là gì?",
            "Phương trình lượng giác cơ bản",
            (
                ("A", "x = kπ, k ∈ ℤ", True, None),
                ("B", "x = π/2 + kπ, k ∈ ℤ", False, "nhầm với cos x = 0"),
                ("C", "x = k2π, k ∈ ℤ", False, "thiếu một nửa số nghiệm"),
                ("D", "x = π/2 + k2π, k ∈ ℤ", False, "nhầm với sin x = 1"),
            ),
            (
                ("Đường tròn lượng giác", "Tung độ bằng 0 tại hai điểm 0 và π, lặp lại sau mỗi π."),
                ("Đồ thị", "Đồ thị y = sin x cắt trục hoành tại mọi bội của π."),
            ),
            Twin(
                "Phương trình cos x = 0 có nghiệm là gì?",
                (
                    ("A", "x = π/2 + kπ, k ∈ ℤ", True, None),
                    ("B", "x = kπ, k ∈ ℤ", False, "nhầm với sin x = 0"),
                    ("C", "x = π/2 + k2π, k ∈ ℤ", False, "thiếu một nửa số nghiệm"),
                    ("D", "x = k2π, k ∈ ℤ", False, "nhầm với cos x = 1"),
                ),
            ),
        ),
        Item(
            "Chu kì tuần hoàn của hàm số y = sin 2x là bao nhiêu?",
            "Chu kì của hàm lượng giác",
            (
                ("A", "π", True, None),
                ("B", "2π", False, "quên chia cho hệ số của x"),
                ("C", "4π", False, "nhân với hệ số thay vì chia"),
                ("D", "π/2", False, "chia cho hệ số hai lần"),
            ),
            (
                ("Công thức", "y = sin(ax) có chu kì 2π/|a|; ở đây 2π/2 = π."),
                ("Kiểm lại", "sin 2(x + π) = sin(2x + 2π) = sin 2x."),
            ),
            Twin(
                "Chu kì tuần hoàn của hàm số y = cos 3x là bao nhiêu?",
                (
                    ("A", "2π/3", True, None),
                    ("B", "2π", False, "quên chia cho hệ số của x"),
                    ("C", "6π", False, "nhân với hệ số thay vì chia"),
                    ("D", "π/3", False, "lấy π chia cho hệ số"),
                ),
            ),
        ),
        Item(
            "Cho cos α = 3/5 với α là góc nhọn. Tính sin α.",
            "Hệ thức lượng giác cơ bản",
            (
                ("A", "4/5", True, None),
                ("B", "−4/5", False, "quên rằng góc nhọn có sin dương"),
                ("C", "2/5", False, "lấy 1 − cos α"),
                ("D", "16/25", False, "quên lấy căn bậc hai"),
            ),
            (
                ("Hệ thức", "sin²α = 1 − cos²α = 16/25, α nhọn nên sin α = 4/5."),
                ("Tam giác vuông", "Cạnh kề 3, cạnh huyền 5 thì cạnh đối là 4."),
            ),
            Twin(
                "Cho sin α = 5/13 với α là góc nhọn. Tính cos α.",
                (
                    ("A", "12/13", True, None),
                    ("B", "−12/13", False, "quên rằng góc nhọn có cos dương"),
                    ("C", "8/13", False, "lấy 1 − sin α"),
                    ("D", "144/169", False, "quên lấy căn bậc hai"),
                ),
            ),
        ),
        Item(
            "Nghiệm của phương trình 2cos x − 1 = 0 trên đoạn [0; π] là gì?",
            "Phương trình lượng giác trên một đoạn",
            (
                ("A", "x = π/3", True, None),
                ("B", "x = π/6", False, "nhầm giá trị của sin với cos"),
                ("C", "x = 2π/3", False, "sai dấu khi chuyển vế"),
                ("D", "x = π/2", False, "coi phương trình là cos x = 0"),
            ),
            (
                ("Đưa về cơ bản", "cos x = 1/2, trên [0; π] chỉ có x = π/3."),
                ("Đường tròn", "Hoành độ 1/2 ứng với ±π/3; chỉ π/3 nằm trong đoạn."),
            ),
            Twin(
                "Nghiệm của phương trình 2sin x − √3 = 0 trên đoạn [0; π/2] là gì?",
                (
                    ("A", "x = π/3", True, None),
                    ("B", "x = π/6", False, "nhầm giá trị của sin với cos"),
                    ("C", "x = 2π/3", False, "lấy nghiệm nằm ngoài đoạn"),
                    ("D", "x = π/4", False, "lấy giá trị của góc π/4"),
                ),
            ),
        ),
    ),
)

_SEQUENCES = Topic(
    "11",
    "Cấp số cộng và cấp số nhân",
    (
        Item(
            "Cấp số cộng có u₁ = 2 và công sai d = 3. Tính u₅.",
            "Số hạng tổng quát của cấp số cộng",
            (
                ("A", "14", True, None),
                ("B", "17", False, "dùng n·d thay cho (n − 1)·d"),
                ("C", "11", False, "dùng (n − 2)·d"),
                ("D", "30", False, "nhân thay vì cộng"),
            ),
            (
                ("Công thức", "uₙ = u₁ + (n − 1)d = 2 + 4 · 3 = 14."),
                ("Cộng dần", "2, 5, 8, 11, 14."),
            ),
            Twin(
                "Cấp số cộng có u₁ = 5 và công sai d = −2. Tính u₆.",
                (
                    ("A", "−5", True, None),
                    ("B", "−7", False, "dùng n·d thay cho (n − 1)·d"),
                    ("C", "−3", False, "dùng (n − 2)·d"),
                    ("D", "−60", False, "nhân thay vì cộng"),
                ),
            ),
        ),
        Item(
            "Cấp số nhân có u₁ = 3 và công bội q = 2. Tính u₄.",
            "Số hạng tổng quát của cấp số nhân",
            (
                ("A", "24", True, None),
                ("B", "48", False, "dùng qⁿ thay cho qⁿ⁻¹"),
                ("C", "9", False, "cộng như cấp số cộng"),
                ("D", "12", False, "dùng qⁿ⁻²"),
            ),
            (
                ("Công thức", "uₙ = u₁ · qⁿ⁻¹ = 3 · 2³ = 24."),
                ("Nhân dần", "3, 6, 12, 24."),
            ),
            Twin(
                "Cấp số nhân có u₁ = 2 và công bội q = 3. Tính u₄.",
                (
                    ("A", "54", True, None),
                    ("B", "162", False, "dùng qⁿ thay cho qⁿ⁻¹"),
                    ("C", "11", False, "cộng như cấp số cộng"),
                    ("D", "18", False, "dùng qⁿ⁻²"),
                ),
            ),
        ),
        Item(
            "Tính tổng 10 số hạng đầu của cấp số cộng có u₁ = 1 và d = 2.",
            "Tổng n số hạng đầu của cấp số cộng",
            (
                ("A", "100", True, None),
                ("B", "19", False, "chỉ tính u₁₀"),
                ("C", "110", False, "dùng u₁₀ = u₁ + 10d"),
                ("D", "200", False, "quên chia cho 2"),
            ),
            (
                ("Công thức", "Sₙ = n(u₁ + uₙ)/2 = 10 · (1 + 19)/2 = 100."),
                ("Ghép cặp", "Ghép số đầu với số cuối: năm cặp, mỗi cặp 20."),
            ),
            Twin(
                "Tính tổng 8 số hạng đầu của cấp số cộng có u₁ = 3 và d = 4.",
                (
                    ("A", "136", True, None),
                    ("B", "31", False, "chỉ tính u₈"),
                    ("C", "152", False, "dùng u₈ = u₁ + 8d"),
                    ("D", "272", False, "quên chia cho 2"),
                ),
            ),
        ),
        Item(
            "Dãy số nào sau đây là cấp số cộng?",
            "Nhận biết cấp số cộng",
            (
                ("A", "1; 4; 7; 10", True, None),
                ("B", "1; 2; 4; 8", False, "nhầm cấp số nhân với cấp số cộng"),
                ("C", "1; 4; 9; 16", False, "thấy dãy tăng là tưởng cấp số cộng"),
                ("D", "2; 3; 5; 8", False, "chỉ xét hai số hạng đầu"),
            ),
            (
                ("Hiệu liên tiếp", "Cấp số cộng có mọi hiệu uₙ₊₁ − uₙ bằng nhau."),
                ("Trung bình cộng", "Mỗi số hạng giữa bằng trung bình cộng hai số hạng kề."),
            ),
            Twin(
                "Dãy số nào sau đây là cấp số nhân?",
                (
                    ("A", "3; 6; 12; 24", True, None),
                    ("B", "3; 6; 9; 12", False, "nhầm cấp số cộng với cấp số nhân"),
                    ("C", "1; 3; 6; 10", False, "thấy dãy tăng là tưởng cấp số nhân"),
                    ("D", "2; 4; 6; 12", False, "chỉ xét hai số hạng đầu"),
                ),
                (
                    ("Thương liên tiếp", "Cấp số nhân có mọi thương uₙ₊₁ : uₙ bằng nhau."),
                    ("Trung bình nhân", "Bình phương số hạng giữa bằng tích hai số hạng kề."),
                ),
            ),
        ),
        Item(
            "Tính tổng 4 số hạng đầu của cấp số nhân có u₁ = 1 và q = 2.",
            "Tổng n số hạng đầu của cấp số nhân",
            (
                ("A", "15", True, None),
                ("B", "16", False, "lấy qⁿ mà quên trừ 1"),
                ("C", "8", False, "chỉ tính u₄"),
                ("D", "31", False, "cộng thừa một số hạng"),
            ),
            (
                ("Công thức", "Sₙ = u₁(qⁿ − 1)/(q − 1) = (16 − 1)/1 = 15."),
                ("Cộng trực tiếp", "1 + 2 + 4 + 8 = 15."),
            ),
            Twin(
                "Tính tổng 3 số hạng đầu của cấp số nhân có u₁ = 2 và q = 3.",
                (
                    ("A", "26", True, None),
                    ("B", "54", False, "lấy u₁ · qⁿ"),
                    ("C", "18", False, "chỉ tính u₃"),
                    ("D", "80", False, "cộng thừa một số hạng"),
                ),
            ),
        ),
        Item(
            "Ba số x; 5; 9 theo thứ tự lập thành cấp số cộng. Tìm x.",
            "Tính chất ba số hạng liên tiếp",
            (
                ("A", "1", True, None),
                ("B", "7", False, "lấy trung bình cộng của 5 và 9"),
                ("C", "−1", False, "sai dấu khi chuyển vế"),
                ("D", "4", False, "lấy công sai làm số hạng"),
            ),
            (
                ("Số hạng giữa", "5 = (x + 9)/2 nên x = 1."),
                ("Công sai", "d = 9 − 5 = 4, nên x = 5 − 4 = 1."),
            ),
            Twin(
                "Ba số dương 2; x; 18 theo thứ tự lập thành cấp số nhân. Tìm x.",
                (
                    ("A", "6", True, None),
                    ("B", "10", False, "dùng trung bình cộng thay cho trung bình nhân"),
                    ("C", "9", False, "chia số hạng cuối cho số hạng đầu"),
                    ("D", "36", False, "nhân hai số hạng mà quên lấy căn"),
                ),
                (
                    ("Số hạng giữa", "x² = 2 · 18 = 36, x dương nên x = 6."),
                    ("Công bội", "q² = 18/2 = 9, q = 3, nên x = 2 · 3 = 6."),
                ),
            ),
        ),
    ),
)

_DEMO_TWINS = (
    Twin(
        "Đạo hàm của y = x³ − 2x là gì?",
        (
            ("A", "3x² − 2", True, None),
            ("B", "x² − 2", False, "quên nhân số mũ khi hạ bậc"),
            ("C", "3x²", False, "bỏ sót đạo hàm của số hạng bậc nhất"),
            ("D", "x³ − 2", False, "chỉ đạo hàm một số hạng"),
        ),
        (
            ("Công thức luỹ thừa", "(xⁿ)′ = n·xⁿ⁻¹, áp cho từng số hạng rồi cộng lại."),
            ("Kiểm bằng hệ số góc", "Tính hệ số góc tiếp tuyến tại một điểm và đối chiếu."),
        ),
    ),
    Twin(
        "Hàm số y = −3x + 2 nghịch biến trên khoảng nào?",
        (
            ("A", "Khoảng (−∞; +∞)", True, None),
            ("B", "Khoảng (0; +∞)", False, "tưởng hàm bậc nhất chỉ giảm khi x dương"),
            ("C", "Khoảng (−∞; 0)", False, "đọc ngược chiều biến thiên"),
            ("D", "Không nghịch biến ở đâu", False, "nhầm hệ số góc âm với hàm hằng"),
        ),
        (
            ("Hệ số góc", "y′ = −3 < 0 với mọi x, nên hàm nghịch biến trên toàn trục số."),
            ("Đồ thị", "Đường thẳng có hệ số góc âm đi xuống trên toàn miền xác định."),
        ),
    ),
    Twin(
        "Giới hạn của (x² − 4)/(x − 2) khi x → 2 bằng bao nhiêu?",
        (
            ("A", "4", True, None),
            ("B", "0", False, "thay thẳng x = 2 vào tử rồi dừng"),
            ("C", "2", False, "rút gọn sai khi phân tích hiệu hai bình phương"),
            ("D", "Không tồn tại", False, "coi dạng 0/0 là không có giới hạn"),
        ),
        (
            ("Phân tích thành nhân tử", "(x² − 4) = (x − 2)(x + 2), rút gọn rồi thay x = 2."),
            ("Quy tắc L'Hôpital", "Đạo hàm tử và mẫu: 2x / 1, thay x = 2 được 4."),
        ),
    ),
    Twin(
        "Cho hàm số y = x³ − 12x. Hàm số nghịch biến trên khoảng nào?",
        (
            ("A", "Khoảng (−2; 2)", True, None),
            ("B", "Khoảng (−∞; −2)", False, "đọc ngược khoảng đồng biến và nghịch biến"),
            ("C", "Khoảng (0; 3)", False, "chỉ thử một điểm rồi suy ra cả khoảng"),
            ("D", "Khoảng (−3; 0)", False, "lấy khoảng chứa cả phần tăng lẫn phần giảm"),
        ),
        (
            ("Xét dấu đạo hàm", "y′ = 3x² − 12 < 0 khi −2 < x < 2."),
            ("Bảng biến thiên", "Lập bảng với hai điểm tới hạn x = ±2 rồi đọc chiều."),
        ),
    ),
    Twin(
        "Đồ thị y = (3x + 2)/(x − 1) có tiệm cận ngang là đường nào?",
        (
            ("A", "y = 3", True, None),
            ("B", "x = 1", False, "nhầm tiệm cận đứng với tiệm cận ngang"),
            ("C", "y = −2", False, "lấy tỉ số hai hằng số thay vì hai hệ số bậc cao nhất"),
            ("D", "y = 0", False, "áp quy tắc của trường hợp bậc tử nhỏ hơn bậc mẫu"),
        ),
        (
            ("Tỉ số hệ số bậc cao nhất", "Bậc tử bằng bậc mẫu nên tiệm cận ngang là 3/1 = 3."),
            ("Lấy giới hạn", "Cho x → ±∞, chia cả tử và mẫu cho x rồi lấy giới hạn."),
        ),
    ),
    Twin(
        "Giá trị nhỏ nhất của y = x + 9/x trên (0; +∞) bằng bao nhiêu?",
        (
            ("A", "6", True, None),
            ("B", "1", False, "lấy hệ số của x thay cho giá trị nhỏ nhất"),
            ("C", "3", False, "lấy giá trị của x tại điểm cực tiểu thay cho giá trị của y"),
            ("D", "0", False, "coi hàm giảm mãi nên không có giá trị nhỏ nhất dương"),
        ),
        (
            ("Đạo hàm", "y′ = 1 − 9/x² = 0 cho x = 3, thay lại được y(3) = 6."),
            ("Bất đẳng thức Cô-si", "x + 9/x ≥ 2√9 = 6 với x > 0, dấu bằng khi x = 3."),
        ),
    ),
)

_FUNCTIONS = Topic(
    "12",
    "Hàm số",
    tuple(
        Item(stem, objective, options, methods, twin)
        for (stem, objective, options, methods), twin in zip(
            DEMO_QUESTIONS, _DEMO_TWINS, strict=True
        )
    ),
)

_EXPONENTS = Topic(
    "12",
    "Mũ và logarit",
    (
        Item(
            "log₂ 8 bằng bao nhiêu?",
            "Định nghĩa logarit",
            (
                ("A", "3", True, None),
                ("B", "4", False, "chia 8 cho cơ số"),
                ("C", "256", False, "nhầm logarit với luỹ thừa"),
                ("D", "1/3", False, "đảo ngược kết quả"),
            ),
            (
                ("Định nghĩa", "log₂ 8 = x nghĩa là 2ˣ = 8, nên x = 3."),
                ("Viết thành luỹ thừa", "8 = 2³, nên log₂ 2³ = 3."),
            ),
            Twin(
                "log₃ 81 bằng bao nhiêu?",
                (
                    ("A", "4", True, None),
                    ("B", "27", False, "chia 81 cho cơ số"),
                    ("C", "3⁸¹", False, "nhầm logarit với luỹ thừa"),
                    ("D", "1/4", False, "đảo ngược kết quả"),
                ),
            ),
        ),
        Item(
            "Rút gọn 2³ · 2⁴.",
            "Tính chất của luỹ thừa",
            (
                ("A", "2⁷", True, None),
                ("B", "2¹²", False, "nhân số mũ thay vì cộng"),
                ("C", "4⁷", False, "nhân cả hai cơ số"),
                ("D", "2¹", False, "trừ số mũ khi nhân"),
            ),
            (
                ("Quy tắc", "aᵐ · aⁿ = aᵐ⁺ⁿ, nên 2³ · 2⁴ = 2⁷."),
                ("Tính số", "8 · 16 = 128 = 2⁷."),
            ),
            Twin(
                "Rút gọn 3⁵ : 3².",
                (
                    ("A", "3³", True, None),
                    ("B", "3¹⁰", False, "nhân số mũ thay vì trừ"),
                    ("C", "1³", False, "chia cả hai cơ số"),
                    ("D", "3⁷", False, "cộng số mũ khi chia"),
                ),
                (
                    ("Quy tắc", "aᵐ : aⁿ = aᵐ⁻ⁿ, nên 3⁵ : 3² = 3³."),
                    ("Tính số", "243 : 9 = 27 = 3³."),
                ),
            ),
        ),
        Item(
            "Tập xác định của hàm số y = log(x − 2) là tập nào?",
            "Tập xác định của hàm logarit",
            (
                ("A", "(2; +∞)", True, None),
                ("B", "[2; +∞)", False, "cho biểu thức trong logarit bằng 0"),
                ("C", "ℝ", False, "quên điều kiện của logarit"),
                ("D", "(−∞; 2)", False, "giải ngược chiều bất phương trình"),
            ),
            (
                ("Điều kiện", "Biểu thức trong logarit phải dương: x − 2 > 0."),
                ("Thử điểm", "x = 2 làm log 0 vô nghĩa, nên đầu mút 2 bị loại."),
            ),
            Twin(
                "Tập xác định của hàm số y = ln(3 − x) là tập nào?",
                (
                    ("A", "(−∞; 3)", True, None),
                    ("B", "(−∞; 3]", False, "cho biểu thức trong logarit bằng 0"),
                    ("C", "ℝ", False, "quên điều kiện của logarit"),
                    ("D", "(3; +∞)", False, "giải ngược chiều bất phương trình"),
                ),
            ),
        ),
        Item(
            "Nghiệm của phương trình 2ˣ = 16 là gì?",
            "Phương trình mũ cơ bản",
            (
                ("A", "x = 4", True, None),
                ("B", "x = 8", False, "chia 16 cho cơ số"),
                ("C", "x = 2", False, "lấy căn bậc hai"),
                ("D", "x = 32", False, "nhân 16 với cơ số"),
            ),
            (
                ("Cùng cơ số", "16 = 2⁴, nên 2ˣ = 2⁴ và x = 4."),
                ("Lấy logarit", "x = log₂ 16 = 4."),
            ),
            Twin(
                "Nghiệm của phương trình 3ˣ⁻¹ = 9 là gì?",
                (
                    ("A", "x = 3", True, None),
                    ("B", "x = 2", False, "quên trừ 1 ở số mũ"),
                    ("C", "x = 1", False, "trừ 1 hai lần"),
                    ("D", "x = 10", False, "cộng 9 với 1"),
                ),
                (
                    ("Cùng cơ số", "9 = 3², nên x − 1 = 2 và x = 3."),
                    ("Lấy logarit", "x − 1 = log₃ 9 = 2."),
                ),
            ),
        ),
        Item(
            "Tính log 2 + log 5.",
            "Logarit của một tích",
            (
                ("A", "1", True, None),
                ("B", "log 7", False, "cộng hai biểu thức trong logarit"),
                ("C", "10", False, "quên lấy logarit của tích"),
                ("D", "log 2 · log 5", False, "nhầm tổng thành tích"),
            ),
            (
                ("Quy tắc", "log a + log b = log(ab) = log 10 = 1."),
                ("Kiểm lại", "10¹ = 10 = 2 · 5."),
            ),
            Twin(
                "Tính log₂ 12 − log₂ 3.",
                (
                    ("A", "2", True, None),
                    ("B", "log₂ 9", False, "trừ hai biểu thức trong logarit"),
                    ("C", "4", False, "quên lấy logarit của thương"),
                    ("D", "log₂ 36", False, "nhầm hiệu thành tích"),
                ),
                (
                    ("Quy tắc", "log a − log b = log(a/b) = log₂ 4 = 2."),
                    ("Kiểm lại", "2² = 4 = 12 : 3."),
                ),
            ),
        ),
        Item(
            "Hàm số nào sau đây đồng biến trên ℝ?",
            "Tính đơn điệu của hàm mũ và logarit",
            (
                ("A", "y = 2ˣ", True, None),
                ("B", "y = (1/2)ˣ", False, "quên rằng cơ số nhỏ hơn 1 thì nghịch biến"),
                ("C", "y = log₂ x", False, "quên tập xác định chỉ là (0; +∞)"),
                ("D", "y = x²", False, "coi mọi hàm luỹ thừa đều đồng biến"),
            ),
            (
                ("Theo cơ số", "y = aˣ đồng biến trên ℝ khi a > 1."),
                ("Tập xác định", "Đồng biến trên ℝ thì trước hết phải xác định trên ℝ."),
            ),
            Twin(
                "Hàm số nào sau đây nghịch biến trên ℝ?",
                (
                    ("A", "y = (1/3)ˣ", True, None),
                    ("B", "y = 3ˣ", False, "quên rằng cơ số lớn hơn 1 thì đồng biến"),
                    ("C", "y = log₁/₃ x", False, "quên tập xác định chỉ là (0; +∞)"),
                    ("D", "y = −x²", False, "coi mọi hàm có dấu trừ đều nghịch biến"),
                ),
                (
                    ("Theo cơ số", "y = aˣ nghịch biến trên ℝ khi 0 < a < 1."),
                    ("Tập xác định", "Nghịch biến trên ℝ thì trước hết phải xác định trên ℝ."),
                ),
            ),
        ),
    ),
)

TOPICS: dict[str, tuple[Topic, Topic]] = {
    "10": (_QUADRATIC, _SETS),
    "11": (_TRIGONOMETRY, _SEQUENCES),
    "12": (_FUNCTIONS, _EXPONENTS),
}
