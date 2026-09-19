## 새로운 Online Judge 추가하기

현재 Study Manager는 URL을 입력받아 해당 문제가 어느 Online Judge(OJ)에 속하는지 판별하고, OJ별 모듈을 통해 문제 메타데이터를 가져오는 구조로 되어 있습니다.

외부에서는 OJ 종류를 직접 신경 쓰지 않고 아래 함수만 사용합니다.

```python
problem = get_problem(url)
```

새로운 OJ를 추가하려면 아래 순서대로 구현하면 됩니다.

### 1. OJ 종류와 URL 파싱 추가

`src/study_manager/routing/problem_url.py`에서 `Judge` enum에 새로운 OJ를 추가합니다.

```python
class Judge(Enum):
    BOJ = "boj"
    CODEFORCES = "codeforces"
    EXAMPLE = "example"
```

그다음 `parse_problem_url()`에서 해당 OJ의 문제 URL을 인식하도록 추가합니다.

```python
if host in {"example.com", "www.example.com"}:
    if ...:
        return ProblemRef(
            judge=Judge.EXAMPLE,
            problem_id=...,
            url=url,
        )
```

`ProblemRef`는 URL을 분석한 결과만 나타냅니다.

```python
@dataclass
class ProblemRef:
    judge: Judge
    problem_id: str
    url: str
```

각 OJ의 문제 식별자가 반드시 정수일 필요는 없으므로 `problem_id`는 문자열을 사용합니다.

### 2. OJ별 모듈 생성

`src/study_manager/judges/` 아래에 새로운 OJ 파일을 생성합니다.

예:

```text
judges/
├─ boj.py
├─ codeforces.py
└─ example.py
```

해당 파일에서 다음 내용을 구현합니다.

- 해당 OJ 또는 관련 API에서 문제 메타데이터 조회
- 해당 OJ에서 사용할 문제 데이터 구조 정의
- `ProblemRef`를 받아 문제 정보를 반환하는 `get_problem()` 구현

예:

```python
from dataclasses import dataclass

from study_manager.routing.problem_url import Judge, ProblemRef


@dataclass
class ExampleProblem:
    problem_id: str
    title: str
    difficulty: str | None
    tags: list[str]
    url: str


def get_problem(ref: ProblemRef) -> ExampleProblem:
    if ref.judge != Judge.EXAMPLE:
        raise ValueError("Example OJ 문제가 아닙니다.")

    # API 호출 또는 페이지 조회
    # 필요한 데이터 가공

    return ExampleProblem(
        problem_id=ref.problem_id,
        title=...,
        difficulty=...,
        tags=...,
        url=ref.url,
    )
```

각 OJ가 제공하는 정보는 서로 다르므로 기존 OJ와 동일한 데이터 포맷을 강제할 필요는 없습니다.

예를 들어 BOJ와 Codeforces는 서로 다른 구조를 사용합니다.

```text
BojProblem
├─ problem_id
├─ title
├─ tier
├─ tags
└─ url
```

```text
CodeforcesProblem
├─ contest_id
├─ index
├─ title
├─ rating
├─ tags
└─ url
```

새 OJ도 해당 OJ에 자연스러운 데이터 구조를 사용하면 됩니다.

### 3. Dispatcher에 등록

`src/study_manager/judges/__init__.py`에 새 OJ 모듈을 추가합니다.

```python
from study_manager.judges import boj, codeforces, example
```

그리고 `handlers`에 등록합니다.

```python
handlers = {
    Judge.BOJ: boj.get_problem,
    Judge.CODEFORCES: codeforces.get_problem,
    Judge.EXAMPLE: example.get_problem,
}
```

이 과정을 완료하면 외부 코드에서는 기존과 동일하게 다음 코드만 사용하면 됩니다.

```python
problem = get_problem(url)
```

`get_problem()` 내부에서 URL을 분석하고 적절한 OJ 모듈을 자동으로 선택합니다.

### 4. 동작 확인

테스트할 문제 URL을 `main.py`에 추가합니다.

```python
urls = [
    "https://...",
]
```

프로젝트 루트에서 실행합니다.

```bash
python -m study_manager.main
```

추가한 OJ의 문제 정보가 정상적으로 출력되면 기본 연동은 완료된 것입니다.

### 5. Notion 연동 추가

OJ별 Notion 데이터베이스 구조는 서로 다를 수 있습니다.

따라서 새로운 OJ를 추가할 때 기존 BOJ 또는 Codeforces 데이터베이스 구조에 맞추려고 하지 말고, 해당 OJ의 실제 데이터와 동아리 운영 방식에 맞게 저장 로직을 구현합니다.

예:

```text
notion/
├─ boj.py
├─ codeforces.py
└─ example.py
```

각 모듈에서는 해당 OJ의 문제 객체를 해당 Notion 데이터베이스 속성에 맞게 변환합니다.

### 설계 원칙

이 프로젝트는 모든 OJ의 문제 정보를 하나의 공통 `Problem` 구조로 강제하지 않습니다.

공통화하는 범위는 다음 정도로 제한합니다.

```text
문제 URL
→ OJ 판별
→ OJ별 문제 정보 조회
→ OJ별 문제 객체 반환
```

OJ마다 문제 번호 체계, 난이도 체계, 태그, 대회 정보 등 제공하는 메타데이터가 다르기 때문에 각 OJ의 특성을 그대로 유지하는 것을 우선합니다.

새로운 OJ를 추가할 때도 불필요한 공통화를 먼저 시도하기보다, 기존 `boj.py`, `codeforces.py`처럼 해당 OJ의 로직을 하나의 파일에서 이해할 수 있도록 구현하는 것을 권장합니다.