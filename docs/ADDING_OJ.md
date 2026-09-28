# 새로운 Online Judge 추가 가이드

이 문서는 `study-manager`에 새로운 Online Judge(OJ)를 추가하는 방법을 설명합니다.

현재 프로젝트는 다음 흐름으로 동작합니다.

```text
Discord에서 /문제등록 후 스터디 URL 및 문제 URL 입력
        ↓
routing/problem_url.py
URL을 보고 OJ와 문제 ID 판별
        ↓
judges/<oj>.py
OJ에서 문제 메타데이터 수집
        ↓
notion/<oj>.py
Notion 문제 DB 생성/갱신
        ↓
registration.py
스터디 relation 연결
        ↓
스터디 페이지의 OJ별 View 생성/갱신
        ↓
Discord 결과 출력
```

현재 지원 OJ는 다음과 같습니다.

- BOJ
- Codeforces
- Codeforces Gym
- Programmers

새로운 OJ를 추가할 때는 기존 OJ 중 구조가 가장 비슷한 구현을 참고하는 것이 가장 빠릅니다.

- 숫자 문제 ID + 난이도: `Programmers`
- 숫자 문제 ID + 난이도 + 태그: `BOJ`
- 문자열 문제 ID, 여러 URL 형식, 특수 문제 유형: `Codeforces`

---

# 1. 먼저 문제의 고유 ID를 결정한다

코드를 작성하기 전에 해당 OJ에서 문제 하나를 무엇으로 식별할 것인지 결정해야 합니다.

문제 ID는 가능하면 다음 조건을 만족해야 합니다.

- 문제마다 유일해야 한다.
- 시간이 지나도 바뀌지 않아야 한다.
- 문제 제목과 무관해야 한다.
- URL 또는 OJ API에서 안정적으로 얻을 수 있어야 한다.

현재 프로젝트의 예시는 다음과 같습니다.

| OJ | 문제 식별자 예시 |
| --- | --- |
| BOJ | `1000` |
| Codeforces | `1324F` |
| Codeforces Gym | `G-102644C` |
| Programmers | `118668` |

문제 제목을 ID로 사용하지 않습니다.

제목은 변경될 수 있고 서로 다른 문제가 같은 제목을 가질 수도 있습니다.

예를 들어 Programmers URL은 다음과 같습니다.

```text
https://school.programmers.co.kr/learn/courses/30/lessons/118668
```

여기에는 `course_id=30`과 `lesson_id=118668`이 모두 들어 있지만 실제 문제를 식별하는 값은 `118668`입니다.

---

# 2. URL Parser에 새로운 OJ를 등록한다

수정 파일:

```text
src/study_manager/routing/problem_url.py
```

먼저 `Judge` enum에 새로운 OJ를 추가합니다.

예를 들어 Jungol을 추가한다면:

```python
class Judge(Enum):
    BOJ = "boj"
    CODEFORCES = "codeforces"
    PROGRAMMERS = "programmers"
    JUNGOL = "jungol"
```

그 다음 해당 사이트의 URL을 인식하는 parser를 추가합니다.

최종적으로 URL을 넣었을 때 다음과 같은 `ProblemRef`가 나와야 합니다.

```python
ProblemRef(
    judge=Judge.JUNGOL,
    problem_id="1234",
    url="https://...",
)
```

같은 문제에 여러 URL 형식이 존재한다면 가능한 형식을 모두 지원하는 것을 권장합니다.

예를 들어 Codeforces에서는 다음 두 URL이 같은 문제입니다.

```text
https://codeforces.com/problemset/problem/1324/F
https://codeforces.com/contest/1324/problem/F
```

둘 다 같은:

```text
1324F
```

로 파싱됩니다.

URL의 query parameter가 문제 identity와 관계없다면 무시합니다.

예:

```text
https://example.com/problem/1234?from=search
```

에서 `from=search`는 문제 ID에 포함시키지 않습니다.

OJ 내부에 일반 문제와 별도의 문제 종류가 존재한다면 `ProblemRef`에 필요한 정보를 추가할 수 있습니다.

현재 Codeforces Gym이 이 방식을 사용합니다.

```python
ProblemRef(
    judge=Judge.CODEFORCES,
    problem_id="102644C",
    url="...",
    is_gym=True,
)
```

---

# 3. OJ별 Problem 모델과 문제 정보 수집 코드를 작성한다

새 파일:

```text
src/study_manager/judges/<oj>.py
```

예를 들어 Jungol이라면:

```text
src/study_manager/judges/jungol.py
```

이 파일은 오직:

> 해당 OJ에서 문제 정보를 가져오는 역할

을 담당합니다.

Notion 관련 코드는 여기에 넣지 않습니다.

예:

```python
from dataclasses import dataclass


@dataclass
class JungolProblem:
    problem_id: int
    title: str
    level: str | None
    url: str


def get_problem(url: str) -> JungolProblem:
    ...
```

OJ마다 Problem 구조가 달라도 괜찮습니다.

모든 OJ를 하나의 공통 `Problem` 클래스에 억지로 맞추지 않습니다.

현재도 각 OJ는 서로 다른 정보를 가지고 있습니다.

BOJ:

```text
문제 번호
제목
티어
태그
새싹 여부
레이팅 제외 여부
...
```

Codeforces:

```text
Contest ID
Index
제목
Rating
Tags
Gym 여부
...
```

Programmers:

```text
Lesson ID
제목
Level
```

새로운 OJ도 필요한 데이터만 정의하면 됩니다.

---

# 4. 문제 정보를 어디서 가져올지 결정한다

가능하면 다음 우선순위를 권장합니다.

```text
1. 공식 공개 API
2. 안정적인 외부 API
3. 공개 문제 페이지 HTML parsing
```

현재 프로젝트의 사례는 다음과 같습니다.

## BOJ

BOJ 자체에서 필요한 메타데이터를 직접 얻기 어렵기 때문에 `solved.ac`를 사용합니다.

일반 HTTP 요청이 Cloudflare에 막힌 문제가 있었기 때문에 현재는 `curl_cffi`를 사용합니다.

## Codeforces

일반 문제는 Codeforces 공식 API를 사용합니다.

다만 일부 오래된 문제나 Gym 문제는 API에서 충분한 정보를 얻을 수 없기 때문에 실제 문제 페이지를 parsing하는 fallback이 있습니다.

Codeforces 문제 제목이 러시아어 등 다른 언어로 내려오는 것을 막기 위해 가능한 경우 영어 locale을 명시합니다.

## Programmers

공개 문제 페이지를 parsing하여 Lesson ID, 제목, Level 등을 가져옵니다.

---

# 5. HTML parsing을 사용하는 경우 주의사항

공식 API가 없어서 문제 페이지를 parsing해야 한다면 필요한 최소 데이터만 읽는 것이 좋습니다.

예:

```text
문제 ID
제목
난이도
태그
```

페이지 전체 HTML 구조에 지나치게 의존하면 사이트 UI가 조금만 변경되어도 코드가 깨집니다.

HTTP 요청에는 timeout도 반드시 둡니다.

예:

```python
response = requests.get(
    url,
    impersonate="chrome",
    timeout=10,
)
```

일반적인 `httpx` 요청 등이 차단된다면 현재 BOJ/Programmers 구현처럼 `curl_cffi`를 사용할 수 있습니다.

---

# 6. judges dispatcher에 새로운 OJ를 연결한다

수정 파일:

```text
src/study_manager/judges/__init__.py
```

이 파일은 URL을 보고 실제 OJ별 `get_problem()`으로 전달합니다.

개념적으로 다음과 같은 구조입니다.

```python
def get_problem(url):
    ref = parse_problem_url(url)

    if ref.judge == Judge.BOJ:
        return boj.get_problem(url)

    if ref.judge == Judge.CODEFORCES:
        return codeforces.get_problem(url)

    if ref.judge == Judge.PROGRAMMERS:
        return programmers.get_problem(url)

    if ref.judge == Judge.JUNGOL:
        return jungol.get_problem(url)

    raise ValueError("지원하지 않는 OJ입니다.")
```

이 단계까지 끝났다면 Notion 코드를 작성하기 전에 문제 정보 수집부터 테스트합니다.

예:

```python
from study_manager.judges import get_problem

problem = get_problem(
    "https://새로운-oj의-문제-url"
)

print(problem)
```

여기서 올바른 문제 정보가 출력되어야 합니다.

---

# 7. Notion에 새로운 OJ 전용 문제 DB를 만든다

현재 프로젝트는 OJ마다 별도의 문제 DB를 사용합니다.

예:

```text
백준 문제 데이터베이스
코드포스 문제 데이터베이스
프로그래머스 문제 데이터베이스
정올 문제 데이터베이스
```

새 OJ도 별도 DB를 만드는 것을 기본으로 합니다.

필요한 속성은 OJ마다 다르지만 최소한 다음 속성이 필요합니다.

## 이름

Notion type:

```text
title
```

예:

```text
이름
```

## 문제 ID

예:

```text
문제 번호
```

OJ의 ID 형태에 따라 적절한 Notion type을 선택합니다.

숫자 ID라면:

```text
number
```

예:

```text
1000
118668
```

문자열이 들어간다면:

```text
rich_text
```

예:

```text
1324F
G-102644C
```

## 문제 링크

속성 이름:

```text
문제 링크
```

Notion type:

```text
url
```

## 스터디 relation

속성 이름은 기존 DB들과 동일하게:

```text
📚 스터디 데이터베이스
```

를 사용합니다.

이 속성은 기존 `스터디 데이터베이스`와 Relation으로 연결합니다.

## OJ별 추가 속성

필요하다면 자유롭게 추가합니다.

예:

```text
난이도
티어
레벨
레이팅
태그
```

---

# 8. 새로운 Notion DB에 Integration을 연결한다

DB를 만들었다고 API에서 바로 사용할 수 있는 것은 아닙니다.

새 DB를 기존 Notion Integration:

```text
SOLUTIO Study Manager
```

에 연결해야 합니다.

이 과정을 빼먹으면 Notion API에서 해당 DB에 접근할 수 없습니다.

---

# 9. Data Source ID를 환경 변수에 추가한다

로컬 `.env`에 다음 형식으로 추가합니다.

```text
NOTION_<OJ>_DATA_SOURCE_ID=...
```

예를 들어 Jungol이라면:

```env
NOTION_JUNGOL_DATA_SOURCE_ID=...
```

그리고 반드시 `.env.example`에도 빈 값을 추가합니다.

```env
NOTION_JUNGOL_DATA_SOURCE_ID=
```

실제 Data Source ID나 Token은 GitHub에 올리지 않습니다.

`.env`는 서버별로 따로 관리합니다.

배포 환경에서도 새로운 환경 변수가 필요하므로 서버 또는 GitHub Actions/Docker 설정에도 동일한 변수를 추가해야 합니다.

---

# 10. OJ별 Notion 모듈을 만든다

새 파일:

```text
src/study_manager/notion/<oj>.py
```

예:

```text
src/study_manager/notion/jungol.py
```

가장 비슷한 기존 구현을 복사해서 수정하는 것이 좋습니다.

보통 다음 함수들이 필요합니다.

```python
find_problem(...)
create_problem(...)
update_problem_metadata(...)
save_problem(...)
add_study_relation(...)
rebuild_study_view(...)
sync_study_view(...)
```

---

# 11. find_problem()

Notion DB에서 해당 문제가 이미 존재하는지 찾습니다.

앞에서 정한 문제의 고유 ID를 사용해야 합니다.

예:

```text
BOJ       → 1000
Codeforces → 1324F
Programmers → 118668
```

문제 제목로 검색하지 않습니다.

---

# 12. create_problem()

Notion에 새로운 문제 페이지를 생성합니다.

자동으로 관리할 메타데이터를 넣습니다.

예:

```text
이름
문제 번호
난이도
태그
문제 링크
```

새로운 문제를 처음 등록했을 때만 호출됩니다.

---

# 13. update_problem_metadata()

이미 등록되어 있는 문제라면 새 페이지를 만들지 않고 기존 페이지의 자동 메타데이터만 갱신합니다.

중요한 원칙:

```text
프로그램이 관리하는 정보 → 갱신 가능
사람이 작성한 정보 → 보존
```

자동 갱신 대상으로 적절한 정보:

```text
문제 이름
난이도
레이팅
태그
문제 URL
```

보존해야 하는 정보:

```text
학생 풀이
페이지 본문
스터디 relation
기타 사람이 직접 작성한 데이터
```

기존 페이지를 갱신할 때 relation이나 본문 전체를 덮어쓰지 않습니다.

---

# 14. save_problem()

`save_problem()`은 보통 다음 역할을 합니다.

```text
문제 ID로 검색
        ↓
존재함
        ↓
metadata 갱신

존재하지 않음
        ↓
새 페이지 생성
```

일반적으로 다음처럼 사용합니다.

```python
page, created = save_problem(problem)
```

`created`를 이용해서 Discord에서:

```text
생성
```

또는:

```text
갱신
```

을 표시합니다.

---

# 15. Notion Page Template이 있다면 명시적으로 적용한다

새 OJ 문제 DB가 Page Template을 사용하는 경우 기존 Codeforces 구현을 참고합니다.

개발 과정에서 Notion DB의 "기본 Template" 설정만 믿고 API로 Page를 생성했을 때 Template이 적용되지 않는 경우가 있었습니다.

현재는 필요한 경우 Data Source의 Template ID를 구해서 명시적으로:

```python
"template": {
    "type": "template_id",
    "template_id": template_id,
}
```

를 전달합니다.

새 OJ에 학생 풀이 영역 등의 Template이 필요하다면 이 방식을 사용하는 것을 권장합니다.

---

# 16. 스터디 Relation 연결

공통 relation 코드는 다음 파일에 있습니다.

```text
src/study_manager/notion/relations.py
```

현재 공통 함수로 다음 기능들이 구현되어 있습니다.

```python
get_relation_ids(...)
add_relation(...)
query_pages_by_relation(...)
wait_for_relation(...)
```

새 OJ에서도 relation 로직을 새로 만들기보다는 이 공통 함수를 사용합니다.

Relation 속성 이름은:

```text
📚 스터디 데이터베이스
```

를 사용합니다.

---

# 17. Notion의 eventual consistency를 고려한다

Notion API에서는 relation을 추가한 직후 다음 요청에서 그 relation이 바로 보이지 않을 수 있습니다.

즉:

```text
relation 추가
        ↓
바로 relation 개수 조회
        ↓
아직 이전 상태가 조회됨
```

같은 일이 발생할 수 있습니다.

이 문제 때문에 현재 프로젝트에는:

```python
wait_for_relation(...)
```

이 존재합니다.

새 OJ를 추가할 때도 relation 추가 직후 View를 수정해야 한다면 이 처리 방식을 유지합니다.

이를 제거하면 relation은 정상적으로 추가됐는데 View 이름이:

```text
정올 0
```

처럼 잘못 계산되는 문제가 생길 수 있습니다.

---

# 18. 스터디 페이지의 OJ별 View를 구현한다

각 스터디 페이지에는:

```text
스터디 문제 리스트
```

라는 linked database 영역이 있고 그 안에 OJ별 View가 있습니다.

예:

```text
[백준 7] [코포 3] [프머 2]
```

Jungol을 새로 추가한다면:

```text
[백준 7] [코포 3] [프머 2] [정올 4]
```

처럼 보여야 합니다.

View 관련 공통 코드는:

```text
src/study_manager/notion/views.py
```

에 있습니다.

OJ별 Notion 파일에서는 각 OJ에 맞는 configuration과 filter를 작성합니다.

예:

```python
def _get_view_configuration():
    ...
```

여기에서 다음 등을 설정할 수 있습니다.

```text
표시할 column
숨길 column
column width
filter
sort
```

---

# 19. View 이름의 문제 개수는 실제 relation 기준으로 계산한다

View 이름의 숫자는 Discord에서 이번에 입력한 문제 개수가 아닙니다.

Notion에서 해당 스터디와 실제로 연결되어 있는 문제 수를 기준으로 합니다.

예:

```text
정올 4
```

라면 실제로 그 스터디와 relation으로 연결된 Jungol 문제가 4개여야 합니다.

따라서 `rebuild_study_view()`에서는 해당 OJ DB를 relation으로 query해서 문제 수를 계산합니다.

---

# 20. 문제가 0개라면 해당 OJ View를 제거한다

현재 프로젝트에서는 해당 스터디에 문제가 없는 OJ의 View를 보여주지 않습니다.

예를 들어 실제 문제 개수가:

```text
백준 5
코포 3
프머 0
정올 0
```

이라면 화면에는:

```text
[백준 5] [코포 3]
```

만 남기는 것이 목표입니다.

단, Notion에서는 Database의 마지막 View 하나를 삭제할 수 없습니다.

이 예외 처리는 공통:

```text
src/study_manager/notion/views.py
```

에 들어 있으므로 새 OJ에서 별도로 다시 구현하지 않습니다.

---

# 21. registration.py에 새로운 OJ를 연결한다

수정 파일:

```text
src/study_manager/registration.py
```

이 파일은 Discord와 실제 OJ/Notion 구현 사이의 서비스 계층입니다.

Discord가 각 OJ의 내부 구조를 직접 알아서는 안 됩니다.

새 OJ를 추가했다면 `_get_notion_handler()`에 등록합니다.

개념적으로:

```python
def _get_notion_handler(judge):
    if judge == Judge.BOJ:
        return boj

    if judge == Judge.CODEFORCES:
        return codeforces

    if judge == Judge.PROGRAMMERS:
        return programmers

    if judge == Judge.JUNGOL:
        return jungol

    raise ValueError("지원하지 않는 OJ입니다.")
```

이 부분을 빼먹으면 OJ에서 문제 정보를 가져오는 데 성공하더라도 Notion 저장 단계에서 처리하지 못합니다.

---

# 22. 스터디 View rebuild에도 새로운 OJ를 추가한다

`registration.py`에는 등록이 끝난 뒤 해당 스터디의 OJ View들을 다시 계산하는 코드가 있습니다.

새 OJ도 이 과정에 포함시켜야 합니다.

예:

```python
def _rebuild_study_views(study_page_id):
    ...
    jungol.rebuild_study_view(study_page_id)
```

현재 View rebuild 순서는 Notion의:

```text
마지막 View 삭제 제한
eventual consistency
```

등을 고려해서 구성되어 있습니다.

따라서 새 OJ를 추가할 때 기존 rebuild 흐름 전체를 임의로 단순화하지 않는 것을 권장합니다.

기존 OJ들이 어떤 순서로 rebuild되고 있는지 확인한 뒤 그 구조에 새 OJ를 포함시킵니다.

---

# 23. Discord에서 표시할 이름을 추가한다

수정 파일:

```text
src/study_manager/discord/registration_ui.py
```

현재 Discord에서는 내부 enum 이름 대신 사람이 읽기 쉬운 이름을 사용합니다.

예:

```text
BOJ         → 백준
Codeforces  → 코포
Programmers → 프머
```

새 OJ도 같은 방식으로 추가합니다.

예를 들어 Jungol이라면:

```text
Jungol → 정올
```

를 사용한다고 가정할 수 있습니다.

먼저 `_problem_label()`에 추가합니다.

예:

```python
if ref.judge == Judge.JUNGOL:
    return f"정올 {ref.problem_id}"
```

그리고 `render_result()`의 OJ 이름 처리에도 추가합니다.

예:

```python
elif problem.judge == Judge.JUNGOL:
    judge_name = "정올"
```

입력창 placeholder에 지원 OJ 목록을 써두고 있다면 그것도 갱신합니다.

예:

```text
백준 / 코포 / Gym / 프머 / 정올
```

---

# 24. 테스트는 레이어별로 한다

처음부터 Discord에서 모든 기능을 한 번에 테스트하지 않는 것을 권장합니다.

아래 순서대로 테스트하면 어느 부분이 잘못됐는지 찾기 쉽습니다.

---

## 24-1. URL Parser 테스트

예:

```python
from study_manager.routing.problem_url import parse_problem_url

ref = parse_problem_url(
    "https://새로운-oj/problem/1234"
)

print(ref)
```

확인할 것:

```text
OJ가 올바르게 인식되는가?
problem_id가 올바른가?
불필요한 query parameter가 제거되는가?
여러 URL 형식을 같은 문제로 인식하는가?
```

---

## 24-2. 문제 metadata 수집 테스트

예:

```python
from study_manager.judges.jungol import get_problem

problem = get_problem(
    "https://새로운-oj/problem/1234"
)

print(problem)
```

확인할 것:

```text
문제 ID
문제 제목
난이도
태그
문제 URL
```

등 필요한 값들이 정상적으로 들어오는가?

---

## 24-3. Notion 저장 테스트

예:

```python
from study_manager.judges.jungol import get_problem
from study_manager.notion.jungol import save_problem

problem = get_problem(
    "https://새로운-oj/problem/1234"
)

page, created = save_problem(problem)

print(page["id"])
print(created)
```

첫 실행에서는:

```text
created == True
```

가 되어야 합니다.

같은 문제를 다시 실행하면:

```text
created == False
```

가 되어야 합니다.

두 번째 실행에서 새로운 중복 페이지가 생기면 안 됩니다.

---

## 24-4. 기존 사용자 데이터 보존 테스트

문제 페이지에 직접 테스트용 내용을 작성합니다.

예:

```text
학생 풀이
메모
본문 내용
스터디 relation
```

그 다음 문제를 다시 `save_problem()` 합니다.

자동 metadata는 갱신되어도 사람이 작성한 내용은 그대로 남아 있어야 합니다.

---

## 24-5. Relation 테스트

테스트용 스터디 하나에 문제를 등록합니다.

확인할 것:

```text
문제 페이지의 📚 스터디 데이터베이스 relation이 추가되는가?
기존 relation이 사라지지 않는가?
```

---

## 24-6. View 테스트

문제가 하나 연결되면 테스트 스터디에:

```text
[정올 1]
```

같은 View가 생성되어야 합니다.

문제를 추가하면:

```text
[정올 2]
```

처럼 실제 relation 수에 맞게 변경되어야 합니다.

해당 OJ 문제가 0개라면 View가 제거되어야 합니다.

---

## 24-7. registration.py 통합 테스트

Discord를 실행하기 전에 `registration.py`를 직접 호출해보는 것도 좋습니다.

확인할 것:

```text
문제 생성/갱신
relation 연결
View rebuild
오류 처리
```

가 한 번에 정상적으로 동작하는가?

---

## 24-8. Discord 최종 테스트

마지막으로 봇을 실행하고:

```text
/문제등록
```

을 사용합니다.

새 OJ URL을 넣었을 때 등록 전 화면에서:

```text
정올 1234
```

처럼 올바르게 표시되는지 확인합니다.

실행 후:

```text
등록 완료

스터디: 1개
문제: 1개

✓ [정올 1234] 문제 제목 - 생성
```

처럼 나오는지 확인합니다.

같은 문제를 다시 실행하면:

```text
✓ [정올 1234] 문제 제목 - 갱신
```

이 되어야 합니다.

---

# 25. 반드시 확인해야 하는 테스트 케이스

새 OJ를 추가하면 최소한 아래 경우를 모두 확인합니다.

## 처음 등록하는 문제

새 Notion 페이지가 생성되어야 합니다.

```text
생성
```

으로 표시되어야 합니다.

## 이미 등록되어 있는 문제

중복 페이지가 생기면 안 됩니다.

기존 페이지가 갱신되어야 합니다.

```text
갱신
```

으로 표시되어야 합니다.

## 같은 URL을 여러 번 입력

같은 문제를 여러 번 생성하지 않아야 합니다.

## 서로 다른 형태의 같은 문제 URL 입력

OJ가 여러 URL 형식을 지원한다면 동일한 문제로 인식되어야 합니다.

## 잘못된 URL

가능하면 전체 등록 작업이 모두 죽는 대신 해당 문제만 오류로 표시되어야 합니다.

## 스터디 없이 문제만 등록

현재 시스템에서는 허용합니다.

이 경우:

```text
문제 DB 생성/갱신
```

까지만 하고 relation과 View 처리는 하지 않습니다.

## 여러 스터디 + 여러 문제

현재 동작은:

```text
모든 문제 × 모든 선택된 스터디
```

입니다.

예:

```text
스터디 2개
문제 3개
```

라면 각 문제를 두 스터디 모두에 연결합니다.

## 빈 줄이 포함된 Discord 입력

Discord에서는 여러 URL을 줄바꿈으로 한 번에 입력할 수 있습니다.

예:

```text
https://problem/1

https://problem/2


https://problem/3
```

빈 줄은 무시되어야 합니다.

---

# 26. 기존에 다른 DB에 들어 있던 문제를 새 OJ DB로 옮기는 경우

새로운 OJ 지원을 추가하면서 기존 문제가 다른 OJ DB에 섞여 있는 경우가 있을 수 있습니다.

실제로 이 프로젝트에서는 과거에:

```text
Codeforces 문제가 BOJ DB에 존재
Programmers 문제가 BOJ DB에 존재
```

했던 데이터를 각각 별도의 DB로 옮긴 적이 있습니다.

이런 migration에서는 문제 metadata만 옮기면 안 됩니다.

반드시 다음 항목을 함께 확인해야 합니다.

```text
문제 metadata
학생 풀이
페이지 본문
스터디 relation
```

새 DB로 문제를 옮긴 뒤에는 기존 스터디들의 View도 다시 rebuild해야 합니다.

Relation을 새 DB에 옮겼다고 해서 기존 View가 자동으로 완벽하게 정상화된다고 가정하지 않습니다.

---

# 27. 배포 시 확인할 것

현재 프로젝트는 GitHub에 push된 코드를 서버에서 자동으로 배포하는 구조를 사용합니다.

새 OJ를 추가한 코드 자체는 기존 배포 흐름을 따르면 됩니다.

다만 새로운 환경 변수가 추가되었다면 코드만 push해서는 안 됩니다.

예:

```text
NOTION_JUNGOL_DATA_SOURCE_ID
```

같은 값은 실제 배포 서버의 환경 변수에도 추가해야 합니다.

즉 새 OJ 추가 시:

```text
코드 변경
+
Notion DB 생성
+
Integration 연결
+
배포 환경 변수 추가
```

가 모두 필요합니다.

Token이나 실제 Data Source ID를 GitHub 코드에 직접 작성하지 않습니다.

---

# 28. 새 OJ 추가 체크리스트

새 OJ를 추가할 때 아래 체크리스트를 순서대로 확인합니다.

```text
[ ] 문제의 고유 식별자 결정

[ ] Judge enum 추가
[ ] URL parser 추가
[ ] 여러 URL 형식이 있다면 모두 처리

[ ] judges/<oj>.py 생성
[ ] OJ 전용 Problem dataclass 작성
[ ] get_problem() 구현
[ ] timeout 설정
[ ] judges/__init__.py dispatcher 등록

[ ] 문제 metadata 수집 단독 테스트

[ ] Notion OJ 전용 DB 생성
[ ] 이름(title) 속성 생성
[ ] 문제 ID 속성 생성
[ ] 문제 링크(url) 속성 생성
[ ] 필요한 난이도/태그 등의 속성 생성
[ ] 📚 스터디 데이터베이스 relation 생성
[ ] SOLUTIO Study Manager Integration 연결

[ ] NOTION_<OJ>_DATA_SOURCE_ID 환경 변수 추가
[ ] .env.example에도 빈 변수 추가
[ ] 배포 서버에도 실제 환경 변수 추가

[ ] notion/<oj>.py 생성
[ ] find_problem() 구현
[ ] create_problem() 구현
[ ] update_problem_metadata() 구현
[ ] save_problem() 구현
[ ] add_study_relation() 구현
[ ] _get_view_configuration() 구현
[ ] rebuild_study_view() 구현
[ ] sync_study_view() 구현
[ ] 필요한 경우 Notion Template 처리

[ ] 신규 문제 생성 테스트
[ ] 기존 문제 갱신 테스트
[ ] 사용자 작성 데이터 보존 테스트
[ ] relation 테스트
[ ] View 생성/갱신/삭제 테스트

[ ] registration.py에 Notion handler 추가
[ ] registration.py의 View rebuild에 새 OJ 추가

[ ] Discord _problem_label() 추가
[ ] Discord 결과 표시 이름 추가
[ ] Discord placeholder의 지원 OJ 목록 수정

[ ] 스터디 없이 문제만 등록 테스트
[ ] 여러 스터디 + 여러 문제 테스트
[ ] 중복 URL 테스트
[ ] 잘못된 URL 테스트

[ ] /문제등록 최종 테스트

[ ] GitHub push
[ ] 자동 배포 성공 확인
[ ] 실제 Discord에서 배포된 Bot 최종 확인
```

---

# 29. 구현 시 지켜야 할 프로젝트 구조

가능하면 다음 원칙을 유지합니다.

## OJ에서 문제 정보를 가져오는 코드

```text
src/study_manager/judges/<oj>.py
```

에 둡니다.

예:

```text
HTML parsing
공식 API 호출
문제 dataclass
난이도 변환
```

등입니다.

---

## OJ별 Notion 처리

```text
src/study_manager/notion/<oj>.py
```

에 둡니다.

예:

```text
Notion property 변환
문제 검색
생성
갱신
View configuration
```

등입니다.

---

## 공통 Notion 기능

OJ 파일마다 중복 구현하지 않습니다.

현재 공통 기능은 다음 파일들에 있습니다.

```text
src/study_manager/notion/api.py
src/study_manager/notion/relations.py
src/study_manager/notion/views.py
src/study_manager/notion/study.py
```

기능이 여러 OJ에서 동일하게 필요하다면 공통 모듈로 빼는 것을 고려합니다.

---

## Discord에는 OJ의 실제 비즈니스 로직을 넣지 않는다

Discord는:

```text
입력 받기
현재 등록 목록 보여주기
실행 버튼 처리
결과 보여주기
```

만 담당합니다.

실제 등록은:

```text
registration.py
```

를 통해 수행합니다.

즉 구조는:

```text
Discord
   ↓
registration.py
   ↓
judges / notion
```

을 유지합니다.

이렇게 해야 나중에 Discord 외의 UI를 추가하더라도 기존 등록 로직을 그대로 사용할 수 있습니다.

---

# 30. 가장 중요한 유지보수 원칙

## 문제 제목을 ID로 사용하지 않는다

항상 OJ에서 제공하는 안정적인 문제 식별자를 사용합니다.

## 자동 metadata만 덮어쓴다

학생 풀이, 본문, relation 등 사람이 작성한 내용을 가능한 한 보존합니다.

## Data Source ID와 Database ID를 혼동하지 않는다

현재 Notion API에서는 문제 DB query 및 페이지 생성 등에 주로:

```text
data_source_id
```

를 사용합니다.

스터디 페이지 내부 linked database와 View를 다룰 때는:

```text
database_id
```

도 사용합니다.

둘은 같은 값이라고 가정하면 안 됩니다.

## Notion relation은 즉시 반영된다고 가정하지 않는다

필요하면 기존:

```python
wait_for_relation(...)
```

로직을 사용합니다.

## 마지막 Notion View는 삭제할 수 없다는 점을 기억한다

View 생성/삭제 순서를 변경할 때 기존 `views.py`와 rebuild 구현을 먼저 확인합니다.

## 새로운 OJ의 특이한 로직을 공통 코드에 퍼뜨리지 않는다

예를 들어 특정 OJ만 특별한 난이도 체계를 가지고 있다면 가능한 한:

```text
judges/<oj>.py
notion/<oj>.py
```

안에서 해결합니다.

---

# 31. 어떤 기존 구현을 참고할지

새 OJ가 단순한 구조라면:

```text
judges/programmers.py
notion/programmers.py
```

를 먼저 참고합니다.

숫자 ID, 난이도, 태그 등이 있다면:

```text
judges/boj.py
notion/boj.py
```

를 참고합니다.

여러 URL 형식, 문자열 ID, 특수 문제 종류 등 복잡한 구조라면:

```text
judges/codeforces.py
notion/codeforces.py
```

를 참고합니다.

특히 Codeforces는 일반 문제와 Gym 문제를 하나의 OJ 구현에서 함께 처리하므로 비슷한 예외가 있는 OJ를 추가할 때 참고하기 좋습니다.

---

# 32. 향후 개선 가능 사항

현재 구조에서는 새로운 OJ 하나를 추가할 때 여러 파일에 해당 OJ를 등록해야 합니다.

예:

```text
Judge enum
URL parser
judges dispatcher
registration handler
View rebuild
Discord label
Discord result label
```

지원 OJ가 많아지면 한 곳을 빠뜨릴 가능성이 있습니다.

향후 필요하다면 OJ 정보를 하나의 registry로 관리하는 방향을 고려할 수 있습니다.

예:

```python
OJ_REGISTRY = {
    Judge.BOJ: OjConfig(
        display_name="백준",
        notion=boj,
    ),
    Judge.CODEFORCES: OjConfig(
        display_name="코포",
        notion=codeforces,
    ),
    Judge.PROGRAMMERS: OjConfig(
        display_name="프머",
        notion=programmers,
    ),
}
```

이 구조로 리팩터링하면 향후 새 OJ 추가 과정에서 수정해야 하는 파일 수를 줄일 수 있습니다.

다만 현재 구조가 단순하고 정상적으로 동작하고 있으므로, 새로운 OJ가 많이 늘어나기 전까지는 반드시 필요한 작업은 아닙니다.