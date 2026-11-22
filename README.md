# SOLUTIO Study Manager

SOLUTIO 알고리즘 스터디의 문제 등록 및 Notion 연동을 자동화하는 Discord Bot입니다.

Discord에서 스터디 URL과 문제 URL을 입력하면 각 Online Judge에서 문제 정보를 가져와 Notion 문제 DB에 등록하고, 스터디 Relation 및 OJ별 View를 자동으로 갱신합니다.

---

## 지원 Online Judge

- solved.ac (BOJ 및 연계 OJ 문제)
- Codeforces
- Codeforces Gym
- Programmers

---

## 관련 문서

개발 및 운영에 필요한 상세 내용은 아래 문서를 참고하세요.

- [새로운 Online Judge 추가 가이드](docs/ADDING_OJ.md)
- [Notion 설정 및 운영 가이드](docs/NOTION_SETUP.md)
- [solved.ac v4 API 연동 가이드](docs/SOLVEDAC_API.md)

`ADDING_OJ.md`에는 새로운 OJ를 지원하기 위해 수정해야 할 코드와 테스트 절차가 정리되어 있습니다.

`NOTION_SETUP.md`에는 Notion Integration, Data Source, 환경 변수, `NOTION_TOKEN` 관리 및 갱신 절차가 정리되어 있습니다.

---

## 프로젝트 구조

```text
src/study_manager/
├─ discord/          # Discord Bot UI
├─ judges/           # OJ별 문제 정보 수집
├─ notion/           # Notion API 연동
├─ routing/          # 문제 URL 파싱
├─ registration.py   # 문제 등록 전체 흐름
└─ main.py           # 실행 진입점
```

전체적인 문제 등록 흐름은 다음과 같습니다.

```text
Discord
   ↓
URL Parsing
   ↓
OJ 문제 정보 수집
   ↓
Notion 문제 생성 / 갱신
   ↓
스터디 Relation 연결
   ↓
OJ별 View 갱신
```

---

## 개발 환경 설정

Python 3.11 이상이 필요합니다.

저장소를 clone합니다.

```bash
git clone <repository-url>
cd study-manager
```

가상환경을 생성합니다.

```bash
python -m venv .venv
```

### Windows

```powershell
.\.venv\Scripts\Activate.ps1
```

PowerShell 실행 정책 때문에 실행되지 않는 경우:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

### Linux / macOS

```bash
source .venv/bin/activate
```

의존성을 설치합니다.

```bash
python -m pip install -e ".[dev]"
```

---

## 환경 변수

프로젝트 루트의 `.env.example`을 참고하여 `.env` 파일을 생성합니다.

```env
NOTION_TOKEN=
NOTION_STUDY_DATA_SOURCE_ID=
NOTION_SOLVEDAC_DATA_SOURCE_ID=
NOTION_CODEFORCES_DATA_SOURCE_ID=
NOTION_PROGRAMMERS_DATA_SOURCE_ID=

DISCORD_BOT_TOKEN=
DISCORD_GUILD_ID=

SOLVEDAC_CLIENT_ID=
SOLVEDAC_CLIENT_SECRET=
```

실제 Token이나 ID는 GitHub에 커밋하지 않습니다.

`NOTION_SOLVEDAC_DATA_SOURCE_ID`에는 기존 백준 DB를 이름만 변경한 `solved.ac 데이터베이스`의 Data Source ID를 사용합니다. 기존 배포 설정의 `NOTION_BOJ_DATA_SOURCE_ID`도 호환됩니다.

solved.ac v4 API는 [Backstage](https://backstage.solved.ac/developer/apps)에서 발급받은 앱 ID와 시크릿이 필요합니다. 기존 v3 API는 사용하지 않습니다.

solved.ac 문제 URL(`https://solved.ac/p/1000`, `https://solved.ac/p/19917a`)과 백준·DOJ·정올의 숫자 문제 URL을 지원합니다. 연계 OJ의 문제도 같은 solved.ac DB에 저장하며, 스터디 View는 `솔브닥 N`으로 표시합니다. 세부 문제 구분과 기존 페이지 처리 방식은 [연동 가이드](docs/SOLVEDAC_API.md)를 참고하세요.

`.env`는 로컬 개발 환경과 실제 배포 환경에서 각각 별도로 관리합니다.

Notion 환경 변수의 의미, Integration 설정, Token 갱신 방법 등은 [Notion 설정 및 운영 가이드](docs/NOTION_SETUP.md)를 참고하세요.

> **주의:** `NOTION_TOKEN`은 영구적인 값이 아니며 만료될 수 있습니다.  
> 현재 운영 Token의 만료일과 갱신 절차는 `docs/NOTION_SETUP.md`에서 관리합니다.

---

## 실행

가상환경이 활성화된 상태에서 실행합니다.

```bash
python -m study_manager.main
```

정상적으로 실행되면 Discord Bot이 로그인되고 `/문제등록` 명령을 사용할 수 있습니다.

### 전체 문제 정보 갱신

`/스터디관리`는 본인에게만 보이는 관리 메뉴를 엽니다. `운영진` 역할이 있는 사용자에게만 `데베 전체 초기화`, `진행 상황`, `갱신 중단` 버튼이 표시됩니다. 일반 사용자에게는 문제 등록 버튼만 표시됩니다.

`데베 전체 초기화`는 문제를 삭제하지 않고 등록된 문제의 제목·난이도·태그를 갱신합니다. 실행 전 DB별 대상 개수를 확인하며, 풀이·본문·문제 번호·링크·스터디 Relation은 유지합니다.

기본적으로 이름이 정확히 `운영진`인 역할을 확인합니다. 역할 ID를 지정하려면 `DISCORD_STAFF_ROLE_ID`를 설정합니다. 메뉴를 연 뒤 역할이 회수되면 실행할 수 없습니다.

솔브닥·코포·프머 DB 모두 전체 갱신에 포함합니다. 호출 속도를 제한하고 중복 실행을 막으며, 종료 후 10분 동안 재실행을 제한합니다. 프로그래머스 요청은 최소 1초 간격으로 보냅니다.

---

## 배포

현재 프로젝트는 GitHub에 push된 코드를 기준으로 동아리 서버에 자동 배포됩니다.

배포에는 GitHub Actions 및 Docker가 사용되고 있으므로 배포 구조를 수정할 경우 기존 workflow와 Docker 관련 설정을 먼저 확인하세요.

일반적인 코드 수정은 GitHub에 push하면 자동으로 반영됩니다.

단, 새로운 환경 변수를 추가한 경우에는 코드 push만으로는 충분하지 않습니다.

예를 들어 새로운 OJ를 추가하여 다음 환경 변수가 생겼다면:

```text
NOTION_JUNGOL_DATA_SOURCE_ID
```

실제 배포 환경에도 해당 값을 별도로 추가해야 합니다.

Token이나 Data Source ID와 같은 비밀 값은 코드나 GitHub 저장소에 직접 작성하지 않습니다.

---

## 새로운 Online Judge 추가

새로운 OJ 지원을 추가하는 방법은 [새 OJ 추가 가이드](docs/ADDING_OJ.md)를 참고하세요.

OJ를 추가할 때는 대략 다음 영역을 수정하게 됩니다.

```text
URL Parser
OJ 문제 정보 수집
Notion 문제 DB 연동
스터디 View
Registration
Discord 표시
```

구체적인 구현 절차와 테스트 체크리스트는 `ADDING_OJ.md`에 정리되어 있습니다.

> **Tip:** 새로운 OJ를 추가할 때는 사용하는 LLM에게 이 저장소의 GitHub 주소와 [`docs/ADDING_OJ.md`](docs/ADDING_OJ.md)를 함께 제공하는 것을 권장합니다.
>
> 예시 프롬프트:
>
> `이 저장소의 현재 코드와 docs/ADDING_OJ.md를 읽고, <추가할 OJ 이름> 지원을 기존 구조에 맞게 구현해줘. 기존 OJ 구현을 참고하고 필요한 파일 수정과 테스트까지 진행해줘. 문서와 현재 코드가 다르면 현재 코드를 우선해서 판단해줘.`

---

## 문제 해결

문제가 발생하면 증상에 따라 아래 영역부터 확인합니다.

| 증상 | 우선 확인할 곳 |
| --- | --- |
| Discord Bot이 실행되지 않음 | `.env`의 Discord 설정, Discord Application/Bot 설정 |
| 문제 URL을 인식하지 못함 | `src/study_manager/routing/problem_url.py` |
| 특정 OJ의 문제 정보를 가져오지 못함 | `src/study_manager/judges/<oj>.py` |
| Notion API 요청이 실패함 | [`docs/NOTION_SETUP.md`](docs/NOTION_SETUP.md) |
| Notion 문제 속성이 잘못 저장됨 | `src/study_manager/notion/<oj>.py` |
| Relation 또는 View가 이상함 | `src/study_manager/notion/relations.py`, `views.py`, `<oj>.py` |
| 로컬에서는 되지만 서버에서는 안 됨 | 배포 환경 변수, GitHub Actions, Docker 및 배포 로그 |

Notion 관련 문제는 Integration 권한, Data Source ID, Token 등 여러 설정이 관련되어 있으므로 자세한 내용은 [Notion 설정 및 운영 가이드](docs/NOTION_SETUP.md)를 참고하세요.
